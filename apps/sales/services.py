# type: ignore
import json
from types import SimpleNamespace
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounting.services import AccountingService
from apps.catalog.models import Product, ProductHistory, ProductUnitQuantity
from apps.catalog.services import ProductStockService
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import (
    buildCode,
    decimalValue as money,
    decimalValue as quantity,
    jsonsafe,
)
from apps.common.responses import successResponse
from apps.common.domainActions import DomainActionService
from apps.customers.models import (
    Customer,
    CustomerAccountHistory,
    CustomerCoupon,
    CustomerGroup,
    CustomerReward,
)
from apps.settings.services import OptionSettingService, PaymentTypeService
from apps.promotions.models import OrdersCoupon, Coupon, CouponCategory, CouponCustomer, CouponCustomerGroup, CouponProduct
from apps.registers.models import RegistersHistory
from apps.rewards.services import CustomerRewardService
from apps.sales.models import (
    OrderInstalment,
    OrderPayment,
    OrdersProductsRefund,
    OrdersRefund,
    OrdersProduct,
    Order,
)


def getOptionSettings(user):
    option = OptionSettingService.ensureSettings(user)
    return SimpleNamespace(**OptionSettingService.optionValue(option))


def saleDueAmount(sale_order):
    return max(money((sale_order or {}).get("total")) - money((sale_order or {}).get("tendered_amount")), Decimal("0"))


def getCurrentRegisterContext(request, required=True):
    return None


def parseDraftSnapshot(note):
    if not note:
        return {}
    try:
        data = json.loads(note)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"note": note}


class SaleStockService:
    @staticmethod
    def resolveUnitQuantity(product, item, request, required=False):
        where = {"id": item.get("unit_quantity_id"), "product_id": product["id"]} if item.get("unit_quantity_id") else {"product_id": product["id"]}
        unit_quantity = commonQuery.findOneRecord(
            ProductUnitQuantity,
            where,
            request=request,
            tenant_config=True,
        )
        if unit_quantity is None and required:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product selling unit not found.")
        return unit_quantity

    @staticmethod
    def stockEnabled(product):
        return product.get("stock_management") != "disabled" and product.get("type") == "materialized"

    @staticmethod
    def applySaleItem(item, sale_order, request):
        product = commonQuery.findOneRecord(
            Product,
            item["product_id"],
            request=request,
            tenant_config=True,
        )
        if product is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")

        item_qty = quantity(item.get("quantity") or 1)
        if item_qty <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Item quantity must be greater than 0.")

        unit_quantity = None
        unit_id = item.get("unit_id")
        default_unit_price = Decimal("0")
        default_purchase_price = Decimal("0")
        unit_quantity = SaleStockService.resolveUnitQuantity(product, item, request, required=SaleStockService.stockEnabled(product))
        if unit_quantity:
            unit_id = unit_quantity.get("unit_id") or unit_id
            default_unit_price = unit_quantity.get("sale_price") or default_unit_price
            default_purchase_price = unit_quantity.get("cogs") or default_purchase_price

        unit_price = money(item.get("unit_price") if item.get("unit_price") is not None else default_unit_price)
        discount_amount = money(item.get("discount_amount"))
        tax_amount = money(item.get("tax_amount"))
        line_total = (item_qty * unit_price) - discount_amount + tax_amount

        sale_item = commonQuery.createRecord(
            OrdersProduct,
            {
                "sale_order_id": sale_order["id"],
                "product_id": product["id"],
                "unit_id": unit_id,
                "unit_quantity_id": unit_quantity.get("id") if unit_quantity else None,
                "quantity": item_qty,
                "unit_price": unit_price,
                "discount_amount": discount_amount,
                "tax_amount": tax_amount,
                "total": line_total,
                "cost_price": default_purchase_price or 0,
            },
            request=request,
            tenant_config=True,
        )

        if SaleStockService.stockEnabled(product) and unit_quantity:
            ProductStockService.recordStockHistory(
                ProductHistory.ACTION_SOLD,
                {
                    "product_id": product["id"],
                    "order_id": sale_order["id"],
                    "order_product_id": sale_item["id"],
                    "unit_id": unit_quantity.get("unit_id"),
                    "quantity": item_qty,
                    "unit_price": unit_price,
                    "total_price": line_total,
                    "description": f"Sale {sale_order['code']}",
                },
                request,
            )

        return sale_item, line_total, item_qty


class SaleValidationService:
    @staticmethod
    def ensureCustomer(customer_id, request):
        if not customer_id:
            return None
        customer = commonQuery.findOneRecord(
            Customer,
            customer_id,
            request=request,
            tenant_config=True,
        )
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        return customer

    @staticmethod
    def ensureCashChangeSupported(change_amount, cash_paid_amount):
        if change_amount > 0 and cash_paid_amount <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Change can only be returned when cash payment is used.")

    @staticmethod
    def normalizeOrderType(order_type):
        if order_type in ["pos", "take_order", "", None]:
            return "takeaway"
        return order_type

    @staticmethod
    def ensureOrderTypeAllowed(order_type, settings):
        normalized = SaleValidationService.normalizeOrderType(order_type)
        allowed_order_types = [
            "takeaway" if item == "take_order" else item
            for item in (settings.order_types or ["takeaway", "delivery"])
        ]
        if normalized not in allowed_order_types:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "This order type is disabled in business settings.")
        return normalized

    @staticmethod
    def ensurePaymentRules(total, paid_amount, due_amount, customer, settings, request):
        if paid_amount > total:
            return
        if due_amount <= 0:
            return
        if not settings.allow_partial_orders:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Partial or unpaid sales are not allowed.")
        if not customer:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer is required when sale has due amount.")
        if not settings.enable_credit_account:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer credit account is disabled.")
        if customer.get("group_id"):
            group = commonQuery.findOneRecord(
                CustomerGroup,
                customer["group_id"],
                options={"attributes": ["minimal_credit_payment"]},
                request=request,
                tenant_config=True,
            )
            minimum_percentage = money(
                group.get("minimal_credit_payment") if group else 0
            )
            minimum_payment = total * minimum_percentage / Decimal("100")
            if minimum_payment > 0 and paid_amount < minimum_payment:
                raise api_error(
                    400,
                    ErrorCodes.BAD_REQUEST,
                    f"A minimum payment of {minimum_payment:.2f} is required for this customer group.",
                )


class SaleRegisterService:
    @staticmethod
    def recordCashOrderPayment(sale_order, order_payment, shift, amount, request):
        return None

    @staticmethod
    def recordChangeGiven(sale_order, shift, change_amount, request):
        return None


class SaleCustomerAccountService:
    @staticmethod
    def applyAccountPayment(customer, sale_order, amount, payment_note, request):
        balance_before = money(customer.get("account_amount"))
        if balance_before < amount:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer account balance is not enough for this payment.")
        balance_after = balance_before - amount
        Customer.objects.filter(id=customer["id"]).update(account_amount=balance_after)
        customer["account_amount"] = balance_after
        commonQuery.createRecord(
            CustomerAccountHistory,
            {
                "customer_id": customer["id"],
                "amount": amount,
                "previous_amount": balance_before,
                "next_amount": balance_after,
                "operation": "payment",
                "order_id": sale_order["id"],
                "description": payment_note or f"Sale payment for {sale_order['code']}",
            },
            request=request,
            tenant_config=True,
        )


class SaleCouponService:
    @staticmethod
    def normalizeCodes(codes):
        normalized = []
        for code in codes or []:
            value = str(code or "").strip()
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    @staticmethod
    def findIssuedCoupon(code, customer_id, request):
        if not customer_id:
            return None
        return commonQuery.findOneRecord(
            CustomerCoupon,
            {"code": code, "customer_id": customer_id},
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def findBaseCoupon(code, request):
        return commonQuery.findOneRecord(
            Coupon,
            {"code": code},
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def validateCouponTime(coupon):
        now = timezone.localtime()
        if coupon.get("valid_until") and now > coupon["valid_until"]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {coupon.get('code')} has expired.")
        current_time = now.time()
        if coupon.get("valid_hours_start") and current_time < coupon["valid_hours_start"]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {coupon.get('code')} is not active yet.")
        if coupon.get("valid_hours_end") and current_time > coupon["valid_hours_end"]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {coupon.get('code')} is no longer active.")

    @staticmethod
    def validateCouponCustomer(coupon, customer, request):
        coupon_id = coupon["id"]

        customer_links = commonQuery.findAllRecords(
            CouponCustomer,
            {"coupon_id": coupon_id},
            {"attributes": ["customer_id"]},
            request=request,
            tenant_config=True,
        )
        if customer_links:
            if not customer:
                raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {coupon.get('code')} requires a customer.")
            allowed_customer_ids = [item["customer_id"] for item in customer_links]
            if customer["id"] not in allowed_customer_ids:
                raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {coupon.get('code')} is not valid for this customer.")

        group_links = commonQuery.findAllRecords(
            CouponCustomerGroup,
            {"coupon_id": coupon_id},
            {"attributes": ["customer_group_id"]},
            request=request,
            tenant_config=True,
        )
        if group_links:
            if not customer or not customer.get("group_id"):
                raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {coupon.get('code')} requires a customer group.")
            allowed_group_ids = [item["customer_group_id"] for item in group_links]
            if customer["group_id"] not in allowed_group_ids:
                raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {coupon.get('code')} is not valid for this customer group.")

    @staticmethod
    def validateCouponCart(coupon, items, subtotal, request):
        subtotal = money(subtotal)
        minimum_cart_value = money(coupon.get("minimum_cart_value"))
        maximum_cart_value = money(coupon.get("maximum_cart_value"))
        if minimum_cart_value > 0 and subtotal < minimum_cart_value:
            raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {coupon.get('code')} requires minimum cart value {minimum_cart_value}.")
        if maximum_cart_value > 0 and subtotal > maximum_cart_value:
            raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {coupon.get('code')} exceeds maximum cart value.")

        product_ids = list(
            dict.fromkeys(
                item.get("product_id")
                for item in items or []
                if item.get("product_id")
            )
        )
        products = commonQuery.findAllRecords(
            Product,
            {"id__in": product_ids},
            {"attributes": ["id", "category_id"]},
            request=request,
            tenant_config=True,
        )
        category_ids = [
            product["category_id"]
            for product in products
            if product.get("category_id")
        ]

        product_links = commonQuery.findAllRecords(
            CouponProduct,
            {"coupon_id": coupon["id"]},
            {"attributes": ["product_id"]},
            request=request,
            tenant_config=True,
        )
        if product_links:
            required_product_ids = [item["product_id"] for item in product_links]
            if not any(product_id in required_product_ids for product_id in product_ids):
                raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {coupon.get('code')} requires specific products in cart.")

        category_links = commonQuery.findAllRecords(
            CouponCategory,
            {"coupon_id": coupon["id"]},
            {"attributes": ["category_id"]},
            request=request,
            tenant_config=True,
        )
        if category_links:
            required_category_ids = [item["category_id"] for item in category_links]
            if not any(category_id in required_category_ids for category_id in category_ids):
                raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {coupon.get('code')} requires specific categories in cart.")

    @staticmethod
    def computeDiscount(coupon, subtotal):
        subtotal = money(subtotal)
        discount_value = money(coupon.get("discount_value"))
        if coupon.get("type") == "percentage_discount":
            return (subtotal * discount_value) / Decimal("100")
        return discount_value

    @staticmethod
    def assignIssuedCoupon(coupon, customer, request):
        if not customer:
            return None
        issued = commonQuery.findOneRecord(
            CustomerCoupon,
            {"coupon_id": coupon["id"], "customer_id": customer["id"]},
            request=request,
            tenant_config=True,
        )
        if issued:
            return issued
        return commonQuery.createRecord(
            CustomerCoupon,
            {
                "coupon_id": coupon["id"],
                "customer_id": customer["id"],
                "name": coupon.get("name") or "",
                "limit_usage": coupon.get("limit_usage") or 0,
                "code": coupon["code"],
            },
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def applyCoupons(sale_order, coupon_codes, customer, items, subtotal, request):
        total_discount = Decimal("0")
        applied_coupons = []

        for code in SaleCouponService.normalizeCodes(coupon_codes):
            issued_coupon = SaleCouponService.findIssuedCoupon(code, customer.get("id") if customer else None, request)
            coupon = None
            if issued_coupon:
                if issued_coupon.get("status") != 0:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {code} is already redeemed.")
                coupon = commonQuery.findOneRecord(Coupon, issued_coupon["coupon_id"], request=request, tenant_config=True)
            else:
                coupon = SaleCouponService.findBaseCoupon(code, request)

            if coupon is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, f"Coupon {code} not found.")

            SaleCouponService.validateCouponTime(coupon)
            SaleCouponService.validateCouponCustomer(coupon, customer, request)
            SaleCouponService.validateCouponCart(coupon, items, subtotal, request)

            if issued_coupon is None:
                issued_coupon = SaleCouponService.assignIssuedCoupon(coupon, customer, request)

            discount_amount = SaleCouponService.computeDiscount(coupon, subtotal)
            discount_amount = min(discount_amount, money(subtotal) - total_discount)
            if discount_amount <= 0:
                continue

            applied = commonQuery.createRecord(
                OrdersCoupon,
                {
                    "sale_order_id": sale_order["id"],
                    "coupon_id": coupon["id"],
                    "customer_coupon_id": issued_coupon["id"] if issued_coupon else None,
                    "code": code,
                    "name": coupon.get("name") or code,
                    "type": coupon["type"],
                    "discount_value": coupon["discount_value"],
                    "discount_amount": discount_amount,
                },
                request=request,
                tenant_config=True,
            )

            if issued_coupon:
                usage_count = int(issued_coupon.get("usage") or 0) + 1
                update_data = {"usage": usage_count}
                limit_usage = int(coupon.get("limit_usage") or 0)
                if limit_usage > 0 and usage_count >= limit_usage:
                    update_data["status"] = 1
                commonQuery.updateRecordById(
                    CustomerCoupon,
                    issued_coupon["id"],
                    update_data,
                    request=request,
                    tenant_config=True,
                )

            total_discount += discount_amount
            applied_coupons.append(applied)

        return {
            "discount_amount": total_discount,
            "applied_coupons": applied_coupons,
        }


class OrderPaymentService:
    @staticmethod
    def applyPayments(sale_order, payments, shift, customer, settings, request):
        paid_amount = Decimal("0")
        cash_paid_amount = Decimal("0")

        for payment in payments or []:
            amount = money(payment.get("amount"))
            if amount <= 0:
                continue

            payment_type = PaymentTypeService.resolvePaymentType(
                payment.get("payment_type"),
                request,
            )

            if payment_type == "account-payment":
                if not settings.enable_credit_account:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer credit account is disabled.")
                if not customer:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer is required for account payment.")

            order_payment = commonQuery.createRecord(
                OrderPayment,
                {
                    "sale_order_id": sale_order["id"],
                    "identifier": payment_type,
                    "value": amount,
                },
                request=request,
                tenant_config=True,
            )
            paid_amount += amount

            if payment_type == "cash-payment" and shift:
                cash_paid_amount += amount
                SaleRegisterService.recordCashOrderPayment(sale_order, order_payment, shift, amount, request)
            elif payment_type == "account-payment":
                SaleCustomerAccountService.applyAccountPayment(customer, sale_order, amount, payment.get("note"), request)

        return {
            "paid_amount": paid_amount,
            "cash_paid_amount": cash_paid_amount,
        }

    @staticmethod
    def collectDuePayments(sale_order, payments, shift, customer, settings, request):
        paid_amount = Decimal("0")
        cash_paid_amount = Decimal("0")
        payment_ids = []

        for payment in payments or []:
            amount = money(payment.get("amount"))
            if amount <= 0:
                continue

            payment_type = PaymentTypeService.resolvePaymentType(
                payment.get("payment_type"),
                request,
            )

            if payment_type == "account-payment":
                if not settings.enable_credit_account:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer credit account is disabled.")
                if not customer:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer is required for account payment.")

            order_payment = commonQuery.createRecord(
                OrderPayment,
                {
                    "sale_order_id": sale_order["id"],
                    "identifier": payment_type,
                    "value": amount,
                },
                request=request,
                tenant_config=True,
            )
            paid_amount += amount
            payment_ids.append(order_payment["id"])

            if payment_type == "cash-payment" and shift:
                cash_paid_amount += amount
                SaleRegisterService.recordCashOrderPayment(sale_order, order_payment, shift, amount, request)
            elif payment_type == "account-payment":
                SaleCustomerAccountService.applyAccountPayment(customer, sale_order, amount, payment.get("note"), request)

        return {
            "paid_amount": paid_amount,
            "cash_paid_amount": cash_paid_amount,
            "payment_ids": payment_ids,
        }


class SaleCustomerService:
    @staticmethod
    def applyCustomerImpact(sale_order, request):
        customer_id = sale_order.get("customer_id")
        if not customer_id:
            return None

        customer_before = commonQuery.findOneRecord(
            Customer,
            customer_id,
            request=request,
            tenant_config=True,
        )

        due_amount = saleDueAmount(sale_order)
        Customer.objects.filter(id=customer_id).update(
            total_sales=F("total_sales") + sale_order["total"],
            total_sales_count=F("total_sales_count") + 1,
            owed_amount=F("owed_amount") + due_amount,
        )

        if due_amount > 0:
            balance_after = money(customer_before.get("owed_amount") if customer_before else 0) + due_amount
            commonQuery.createRecord(
                CustomerAccountHistory,
                {
                    "customer_id": customer_id,
                    "amount": due_amount,
                    "previous_amount": customer_before.get("owed_amount") if customer_before else 0,
                    "next_amount": balance_after,
                    "operation": "add",
                    "order_id": sale_order["id"],
                    "description": f"Due created for sale {sale_order['code']}",
                },
                request=request,
                tenant_config=True,
            )

        return commonQuery.findOneRecord(
            Customer,
            customer_id,
            request=request,
            tenant_config=True,
        )


class SaleRewardService:
    @staticmethod
    def processRewards(sale_order, request):
        if not sale_order.get("customer_id"):
            return None
        return CustomerRewardService.processSaleReward(
            {
                "customer_id": sale_order["customer_id"],
                "cart_total": sale_order["total"],
                "sale_order_id": sale_order["id"],
                "note": f"Reward earned from sale {sale_order['code']}.",
            },
            request,
        )


class SaleDraftService:
    @staticmethod
    def buildDraftItems(items, request):
        prepared_items = []
        subtotal = Decimal("0")

        for item in items or []:
            product = commonQuery.findOneRecord(
                Product,
                item.get("product_id"),
                request=request,
                tenant_config=True,
            )
            if product is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")

            item_qty = quantity(item.get("quantity") or 1)
            if item_qty <= 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Item quantity must be greater than 0.")

            unit_price = money(item.get("unit_price") if item.get("unit_price") is not None else 0)
            unit_id = item.get("unit_id")
            unit_quantity_id = item.get("unit_quantity_id")
            unit_quantity = SaleStockService.resolveUnitQuantity(product, item, request)
            if unit_quantity:
                unit_id = unit_quantity.get("unit_id") or unit_id
                if item.get("unit_price") is None:
                    unit_price = money(unit_quantity.get("sale_price") or 0)
                unit_quantity_id = unit_quantity.get("id")
            discount_amount = money(item.get("discount_amount"))
            tax_amount = money(item.get("tax_amount"))
            line_total = (item_qty * unit_price) - discount_amount + tax_amount
            subtotal += line_total

            prepared_items.append(
                {
                    "product_id": product["id"],
                    "product_name": product.get("name"),
                    "unit_id": unit_id,
                    "unit_quantity_id": unit_quantity_id,
                    "quantity": item_qty,
                    "unit_price": unit_price,
                    "discount_amount": discount_amount,
                    "tax_amount": tax_amount,
                    "line_total": line_total,
                }
            )

        return {"items": prepared_items, "subtotal": subtotal}

    @staticmethod
    def buildDraftData(draft, request):
        snapshot = parseDraftSnapshot(draft.get("note"))
        customer = None
        if draft.get("customer_id"):
            customer = commonQuery.findOneRecord(
                Customer,
                draft["customer_id"],
                request=request,
                tenant_config=True,
            )
        items = snapshot.get("items") or []
        total_quantity = sum((quantity(item.get("quantity")) for item in items), Decimal("0"))
        return {
            **draft,
            "draft_status": "held" if draft.get("payment_status") == "hold" else draft.get("payment_status"),
            "customer": customer,
            "coupon_codes": snapshot.get("coupon_codes") or [],
            "payments": snapshot.get("payments") or [],
            "note_text": snapshot.get("note") or "",
            "items": items,
            "total_items": len(items),
            "total_quantity": total_quantity,
        }

    @staticmethod
    def reverseAppliedCoupons(sale_order_id, request):
        applied_coupons = commonQuery.findAllRecords(
            OrdersCoupon,
            {"sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "coupon_id",
                    "customer_coupon_id",
                ],
            },
            request=request,
            tenant_config=True,
        )
        for applied in applied_coupons:
            customer_coupon_id = applied.get("customer_coupon_id")
            if not customer_coupon_id:
                continue
            issued_coupon = commonQuery.findOneRecord(
                CustomerCoupon,
                customer_coupon_id,
                request=request,
                tenant_config=True,
            )
            if issued_coupon is None:
                continue
            coupon = None
            if applied.get("coupon_id"):
                coupon = commonQuery.findOneRecord(
                    Coupon,
                    applied["coupon_id"],
                    request=request,
                    tenant_config=True,
                )
            usage_count = max(int(issued_coupon.get("usage") or 0) - 1, 0)
            update_data = {"usage": usage_count}
            if issued_coupon.get("status") != 0 and coupon:
                limit_usage = int(coupon.get("limit_usage") or 0)
                if limit_usage <= 0 or usage_count < limit_usage:
                    update_data["status"] = 0
            commonQuery.updateRecordById(
                CustomerCoupon,
                customer_coupon_id,
                update_data,
                request=request,
                tenant_config=True,
            )

    @staticmethod
    def reverseRewards(sale_order, request):
        customer_id = sale_order.get("customer_id")
        if not customer_id:
            return

        from apps.rewards.services import findMatchingRule, getCustomerRewardSystem

        customer = commonQuery.findOneRecord(
            Customer,
            customer_id,
            request=request,
            tenant_config=True,
        )
        if customer is None:
            return

        reward_system = getCustomerRewardSystem(customer, request)
        if not reward_system:
            return

        rule = findMatchingRule(reward_system["id"], sale_order.get("total"), request)
        earned_points = money(rule.get("reward") or 0) if rule else Decimal("0")
        balance = commonQuery.findOneRecord(
            CustomerReward,
            {"customer_id": customer_id, "reward_id": reward_system["id"]},
            request=request,
            tenant_config=True,
        )
        if balance is None:
            return

        next_points = max(money(balance.get("points") or 0) - earned_points, Decimal("0"))
        commonQuery.updateRecordById(
            CustomerReward,
            balance["id"],
            {
                "points": next_points,
            },
            request=request,
            tenant_config=True,
        )


class SaleVoidService:
    @staticmethod
    def restockSale(sale_order, request):
        items = commonQuery.findAllRecords(
            OrdersProduct,
            {"sale_order_id": sale_order["id"]},
            {
                "attributes": [
                    "id",
                    "product_id",
                    "unit_quantity_id",
                    "quantity",
                    "cost_price",
                ]
            },
            request=request,
            tenant_config=True,
        )
        for item in items:
            product = commonQuery.findOneRecord(
                Product,
                item["product_id"],
                request=request,
                tenant_config=True,
            )
            if not product or not SaleStockService.stockEnabled(product):
                continue
            unit_quantity = SaleStockService.resolveUnitQuantity(product, {"unit_quantity_id": item.get("unit_quantity_id")}, request)
            if unit_quantity is None:
                continue
            restock_qty = quantity(item.get("quantity"))
            ProductStockService.recordStockHistory(
                ProductHistory.ACTION_VOID_RETURN,
                {
                    "product_id": product["id"],
                    "order_id": sale_order["id"],
                    "order_product_id": item["id"],
                    "unit_id": unit_quantity.get("unit_id"),
                    "quantity": restock_qty,
                    "unit_price": item.get("cost_price") or unit_quantity.get("cogs") or 0,
                    "description": f"Void sale {sale_order['code']}",
                },
                request,
            )
            commonQuery.updateRecordById(
                OrdersProduct,
                item["id"],
                {"item_status": "void"},
                request=request,
                tenant_config=True,
            )

    @staticmethod
    def reverseCustomerImpact(sale_order, request):
        customer_id = sale_order.get("customer_id")
        if not customer_id:
            return

        customer = commonQuery.findOneRecord(
            Customer,
            customer_id,
            request=request,
            tenant_config=True,
        )
        if customer is None:
            return

        due_amount = saleDueAmount(sale_order)
        total = money(sale_order.get("total"))
        next_total_sales = max(money(customer.get("total_sales")) - total, Decimal("0"))
        next_total_sales_count = max(int(customer.get("total_sales_count") or 0) - 1, 0)
        next_owed_amount = max(money(customer.get("owed_amount")) - due_amount, Decimal("0"))

        commonQuery.updateRecordById(
            Customer,
            customer_id,
            {
                "total_sales": next_total_sales,
                "total_sales_count": next_total_sales_count,
                "owed_amount": next_owed_amount,
            },
            request=request,
            tenant_config=True,
        )

        if due_amount > 0:
            commonQuery.createRecord(
                CustomerAccountHistory,
                {
                    "customer_id": customer_id,
                    "amount": due_amount,
                    "previous_amount": customer.get("owed_amount") if customer else 0,
                    "next_amount": next_owed_amount,
                    "operation": "deduct",
                    "order_id": sale_order["id"],
                    "description": f"Due reversed for void sale {sale_order['code']}",
                },
                request=request,
                tenant_config=True,
            )


class SaleReturnValidationService:
    @staticmethod
    def ensureSaleOrder(sale_order_id, request):
        sale_order = commonQuery.findOneRecord(
            Order,
            sale_order_id,
            request=request,
            tenant_config=True,
        )
        if sale_order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Sale order not found.")
        if sale_order.get("payment_status") == "void":
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Void sale cannot be returned.")
        return sale_order

    @staticmethod
    def ensureReturnType(return_type):
        if return_type not in ["refund", "exchange", "credit_note"]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid return type.")

    @staticmethod
    def ensureSaleItem(sale_order_id, sale_item_id, request):
        sale_item = commonQuery.findOneRecord(
            OrdersProduct,
            sale_item_id,
            request=request,
            tenant_config=True,
        )
        if sale_item is None or sale_item.get("sale_order_id") != sale_order_id:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Sale item not found.")
        return sale_item

    @staticmethod
    def refundedQuantity(sale_item_id, request):
        records = commonQuery.findAllRecords(
            OrdersProductsRefund,
            {"sale_item_id": sale_item_id},
            {"attributes": ["quantity"]},
            request=request,
            tenant_config=True,
        )
        total = Decimal("0")
        for record in records:
            total += quantity(record.get("quantity"))
        return total

    @staticmethod
    def validateItems(sale_order, items, request):
        if not items:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one return item is required.")

        prepared_items = []
        total_refund = Decimal("0")
        total_tax = Decimal("0")

        for item in items or []:
            sale_item = SaleReturnValidationService.ensureSaleItem(sale_order["id"], item.get("sale_item_id"), request)
            refund_qty = quantity(item.get("quantity"))
            if refund_qty <= 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Refund quantity must be greater than 0.")

            already_refunded = SaleReturnValidationService.refundedQuantity(sale_item["id"], request)
            refundable_qty = quantity(sale_item.get("quantity")) - already_refunded
            if refund_qty > refundable_qty:
                raise api_error(400, ErrorCodes.BAD_REQUEST, f"Refund quantity exceeds remaining refundable quantity for item {sale_item['id']}.")

            unit_price = money(item.get("unit_price") if item.get("unit_price") is not None else sale_item.get("unit_price"))
            original_unit_price = money(sale_item.get("unit_price"))
            if unit_price > original_unit_price:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Refund unit price cannot exceed original unit price.")

            line_total = refund_qty * unit_price
            line_tax = Decimal("0")
            if quantity(sale_item.get("quantity")) > 0 and money(sale_item.get("tax_amount")) > 0:
                line_tax = (money(sale_item.get("tax_amount")) / quantity(sale_item.get("quantity"))) * refund_qty

            total_refund += line_total + line_tax
            total_tax += line_tax
            prepared_items.append(
                {
                    "sale_item": sale_item,
                    "quantity": refund_qty,
                    "unit_price": unit_price,
                    "line_total": line_total,
                    "tax_amount": line_tax,
                    "condition": item.get("condition") or "unspoiled",
                    "note": item.get("note") or "",
                }
            )

        previous_returns = commonQuery.findAllRecords(
            OrdersRefund,
            {"sale_order_id": sale_order["id"]},
            {"attributes": ["total"]},
            request=request,
            tenant_config=True,
        )
        already_refunded_total = sum((money(return_row.get("total")) for return_row in previous_returns), Decimal("0"))
        if already_refunded_total + total_refund > money(sale_order.get("total")):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Refund total exceeds sale total.")

        return {
            "items": prepared_items,
            "subtotal": total_refund - total_tax,
            "tax_amount": total_tax,
            "total": total_refund,
        }


class SaleRefundService:
    @staticmethod
    def updateOrderPaymentStatus(sale_order_id, request):
        sale_order = commonQuery.findOneRecord(Order, sale_order_id, request=request, tenant_config=True)
        if sale_order is None:
            return None
        returns = commonQuery.findAllRecords(
            OrdersRefund,
            {"sale_order_id": sale_order_id},
            {"attributes": ["total"]},
            request=request,
            tenant_config=True,
        )
        refunded_total = sum((money(row.get("total")) for row in returns), Decimal("0"))
        sale_total = money(sale_order.get("total"))
        status = sale_order.get("payment_status")
        if refunded_total <= 0:
            return sale_order
        status = "refunded" if refunded_total >= sale_total else "partially_refunded"
        return commonQuery.updateRecordById(
            Order,
            sale_order_id,
            {"payment_status": status},
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def restoreStock(return_order, prepared_item, request):
        sale_item = prepared_item["sale_item"]
        product = commonQuery.findOneRecord(
            Product,
            sale_item["product_id"],
            request=request,
            tenant_config=True,
        )
        if not product or not SaleStockService.stockEnabled(product):
            return

        unit_quantity = SaleStockService.resolveUnitQuantity(product, {"unit_quantity_id": sale_item.get("unit_quantity_id")}, request)
        if unit_quantity is None:
            return
        refund_qty = prepared_item["quantity"]
        ProductStockService.recordStockHistory(
            ProductHistory.ACTION_RETURNED,
            {
                "product_id": product["id"],
                "order_id": return_order.get("sale_order_id"),
                "order_product_id": sale_item["id"],
                "unit_id": unit_quantity.get("unit_id"),
                "quantity": refund_qty,
                "unit_price": sale_item.get("cost_price") or unit_quantity.get("cogs") or 0,
                "description": f"Sale return {return_order['id']}",
            },
            request,
        )

        if prepared_item["condition"] == "damaged":
            ProductStockService.recordStockHistory(
                ProductHistory.ACTION_DEFECTIVE,
                {
                    "product_id": product["id"],
                    "order_id": return_order.get("sale_order_id"),
                    "order_product_id": sale_item["id"],
                    "unit_id": unit_quantity.get("unit_id"),
                    "quantity": refund_qty,
                    "unit_price": sale_item.get("cost_price") or unit_quantity.get("cogs") or 0,
                    "description": f"Damaged return {return_order['id']}",
                },
                request,
            )

    @staticmethod
    def creditCustomerAccount(customer, sale_order, amount, note, request):
        balance_before = money(customer.get("account_amount"))
        balance_after = balance_before + amount
        Customer.objects.filter(id=customer["id"]).update(account_amount=balance_after)
        commonQuery.createRecord(
            CustomerAccountHistory,
            {
                "customer_id": customer["id"],
                "amount": amount,
                "previous_amount": balance_before,
                "next_amount": balance_after,
                "operation": "refund",
                "order_id": sale_order["id"],
                "description": note or f"Refund for sale {sale_order['code']}",
            },
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def handleRefundSettlement(return_order, sale_order, customer, data, total, settings, request):
        return_type = data.get("return_type") or "refund"
        if total <= 0:
            return {"refund_payment": None, "difference_amount": Decimal("0")}

        if return_type == "credit_note":
            if not settings.enable_credit_account:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer credit account is disabled.")
            if not customer:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer is required for credit note.")
            SaleRefundService.creditCustomerAccount(customer, sale_order, total, data.get("note"), request)
            return {"refund_payment": None, "difference_amount": Decimal("0")}

        if return_type == "exchange":
            difference_amount = Decimal("0")
            if data.get("exchange_sale_id"):
                exchange_sale = commonQuery.findOneRecord(
                    Order,
                    data["exchange_sale_id"],
                    request=request,
                    tenant_config=True,
                )
                if exchange_sale is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Exchange sale not found.")
                difference_amount = money(exchange_sale.get("total")) - total
                if difference_amount < 0 and data.get("payment_type"):
                    total_to_refund = abs(difference_amount)
                    payment_data = {**data, "return_type": "refund"}
                    settlement = SaleRefundService.handleRefundSettlement(return_order, sale_order, customer, payment_data, total_to_refund, settings, request)
                    return {"refund_payment": settlement["refund_payment"], "difference_amount": difference_amount}
            return {"refund_payment": None, "difference_amount": difference_amount}

        payment_type = PaymentTypeService.resolvePaymentType(data.get("payment_type"), request)
        shift = getCurrentRegisterContext(request, required=bool(settings.enable_cash_registers and payment_type == "cash-payment"))
        return_order = commonQuery.updateRecordById(
            OrdersRefund,
            return_order["id"],
            {"payment_method": payment_type},
            request=request,
            tenant_config=True,
        )

        if payment_type == "account-payment":
            if not settings.enable_credit_account:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer credit account is disabled.")
            if not customer:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer is required for account refund.")
            SaleRefundService.creditCustomerAccount(customer, sale_order, total, data.get("note"), request)

        return {"refund_payment": None, "difference_amount": Decimal("0")}


class SaleService:
    @staticmethod
    def listSales(data, request):
        field_config = [
            ["code", True, True],
            ["payment_status", True, True],
            ["order_type", True, True],
            ["customer__full_name", True, False],
            ["user__full_name", True, False],
        ]
        result = commonQuery.fetchPaginatedData(
            Order,
            data,
            field_config,
            {
                "attributes": [
                    "id",
                    "code",
                    "customer_id",
                    "customer__full_name",
                    "user_id",
                    "user__full_name",
                    "register_id",
                    "register__name",
                    "order_type",
                    "payment_status",
                    "subtotal",
                    "discount_amount",
                    "total_coupons",
                    "shipping",
                    "tax_amount",
                    "total",
                    "tendered_amount",
                    "change_amount",
                    "created_at",
                ],
                "order": ["-id"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Sales retrieved successfully.", data=result)

    @staticmethod
    def buildSaleDetail(sale_order_id, request):
        sale_order = commonQuery.findOneRecord(
            Order,
            sale_order_id,
            request=request,
            tenant_config=True,
        )
        if sale_order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Sale order not found.")

        customer = None
        if sale_order.get("customer_id"):
            customer = commonQuery.findOneRecord(
                Customer,
                sale_order["customer_id"],
                request=request,
                tenant_config=True,
            )

        items = commonQuery.findAllRecords(
            OrdersProduct,
            {"sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "product_id",
                    "product__name",
                    "product__sku",
                    "product__barcode",
                    "unit_id",
                    "unit__name",
                    "quantity",
                    "unit_price",
                    "discount_amount",
                    "tax_amount",
                    "total",
                    "cost_price",
                    "item_status",
                ],
                "order": ["id"],
            },
            request=request,
            tenant_config=True,
        )
        for item in items:
            refunded_qty = SaleReturnValidationService.refundedQuantity(item["id"], request)
            sold_qty = quantity(item.get("quantity"))
            item["refunded_quantity"] = refunded_qty
            item["refundable_quantity"] = max(sold_qty - refunded_qty, Decimal("0"))

        sale_order["due_amount"] = saleDueAmount(sale_order)
        sale_order["total_items"] = len(items)
        sale_order["total_quantity"] = sum((quantity(item.get("quantity")) for item in items), Decimal("0"))

        payments = commonQuery.findAllRecords(
            OrderPayment,
            {"sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "identifier",
                    "value",
                    "created_at",
                ],
                "order": ["id"],
            },
            request=request,
            tenant_config=True,
        )

        applied_coupons = commonQuery.findAllRecords(
            OrdersCoupon,
            {"sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "coupon_id",
                    "customer_coupon_id",
                    "code",
                    "type",
                    "discount_value",
                    "discount_amount",
                ],
                "order": ["id"],
            },
            request=request,
            tenant_config=True,
        )

        refunds = commonQuery.findAllRecords(
            OrdersRefund,
            {"sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "sale_order_id",
                    "sale_order__customer_id",
                    "user_id",
                    "user__full_name",
                    "tax_amount",
                    "shipping",
                    "total",
                    "payment_method",
                    "created_at",
                ],
                "order": ["-id"],
            },
            request=request,
            tenant_config=True,
        )
        for refund in refunds:
            refund["items"] = commonQuery.findAllRecords(
                OrdersProductsRefund,
                {"return_order_id": refund["id"]},
                {
                    "attributes": [
                        "id",
                        "sale_item_id",
                        "sale_item__product__name",
                        "quantity",
                        "unit_price",
                        "total",
                        "condition",
                    ],
                    "order": ["id"],
                },
                request=request,
                tenant_config=True,
            )

        totals = {
            "paid_amount": sum((money(payment.get("value")) for payment in payments), Decimal("0")),
            "refunded_amount": sum((money(refund.get("total")) for refund in refunds), Decimal("0")),
        }

        instalments = commonQuery.findAllRecords(
            OrderInstalment,
            {"sale_order_id": sale_order_id},
            {
                "attributes": ["id", "amount", "paid", "payment_id", "date", "created_at"],
                "order": ["date", "id"],
            },
            request=request,
            tenant_config=True,
        )

        return {
            **sale_order,
            "customer": customer,
            "items": items,
            "payments": payments,
            "applied_coupons": applied_coupons,
            "refunds": refunds,
            "totals_summary": totals,
            "instalments": instalments,
        }

    @staticmethod
    def getSale(sale_order_id, request):
        return successResponse(
            "Sale retrieved successfully.",
            data=SaleService.buildSaleDetail(sale_order_id, request),
        )

    @staticmethod
    def getReceipt(sale_order_id, request):
        sale_data = SaleService.buildSaleDetail(sale_order_id, request)
        receipt = {
            "id": sale_data["id"],
            "code": sale_data["code"],
            "created_at": sale_data.get("created_at"),
            "order_type": sale_data.get("order_type"),
            "payment_status": sale_data.get("payment_status"),
            "customer": sale_data.get("customer"),
            "user_id": sale_data.get("user_id"),
            "register_id": sale_data.get("register_id"),
            "subtotal": sale_data.get("subtotal"),
            "discount_amount": sale_data.get("discount_amount"),
            "total_coupons": sale_data.get("total_coupons"),
            "shipping": sale_data.get("shipping"),
            "tax_amount": sale_data.get("tax_amount"),
            "total": sale_data.get("total"),
            "tendered_amount": sale_data.get("tendered_amount"),
            "change_amount": sale_data.get("change_amount"),
            "due_amount": saleDueAmount(sale_data),
            "items": sale_data.get("items") or [],
            "payments": sale_data.get("payments") or [],
            "applied_coupons": sale_data.get("applied_coupons") or [],
        }
        return successResponse("Sale receipt retrieved successfully.", data=receipt)

    @staticmethod
    def hold(data, request):
        if not data.get("items"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one sale item is required.")

        customer = SaleValidationService.ensureCustomer(data.get("customer_id"), request)
        prepared = SaleDraftService.buildDraftItems(data.get("items") or [], request)
        draft = commonQuery.createRecord(
            Order,
            {
                "customer_id": customer["id"] if customer else None,
                "code": buildCode(Order, "hold-cart", data.get("code"), request),
                "order_type": data.get("order_type") or "takeaway",
                "payment_status": "hold",
                "subtotal": prepared["subtotal"],
                "total": prepared["subtotal"],
                "note": json.dumps(
                    jsonsafe(
                        {
                            "note": data.get("note") or "",
                            "coupon_codes": data.get("coupon_codes") or [],
                            "payments": data.get("payments") or [],
                            "items": prepared["items"],
                        }
                    )
                ),
            },
            request=request,
            tenant_config=True,
        )
        return successResponse(
            "Held cart saved successfully.",
            data=SaleDraftService.buildDraftData(draft, request),
        )

    @staticmethod
    def listHeldCarts(data, request):
        filters = dict(data or {})
        filter_data = dict(filters.get("filter") or {})
        filter_data["payment_status"] = "hold"
        filters["filter"] = filter_data
        result = commonQuery.fetchPaginatedData(
            Order,
            filters,
            [["code", True, True], ["customer__full_name", True, False], ["user__full_name", True, False]],
            {
                "attributes": [
                    "id",
                    "code",
                    "customer_id",
                    "customer__full_name",
                    "user_id",
                    "user__full_name",
                    "payment_status",
                    "subtotal",
                    "total",
                    "note",
                    "created_at",
                ],
                "order": ["-id"],
            },
            request=request,
            tenant_config=True,
        )
        result["items"] = [SaleDraftService.buildDraftData(item, request) for item in result["items"]]
        return successResponse("Held carts retrieved successfully.", data=result)

    @staticmethod
    def getHeldCart(draft_id, request):
        draft = commonQuery.findOneRecord(
            Order,
            draft_id,
            request=request,
            tenant_config=True,
        )
        if draft is None or draft.get("payment_status") != "hold":
            raise api_error(404, ErrorCodes.NOT_FOUND, "Held cart not found.")
        return successResponse(
            "Held cart retrieved successfully.",
            data=SaleDraftService.buildDraftData(draft, request),
        )

    @staticmethod
    def deleteHeldCart(draft_id, request):
        draft = commonQuery.findOneRecord(
            Order,
            draft_id,
            request=request,
            tenant_config=True,
        )
        if draft is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Held cart not found.")
        commonQuery.updateRecordById(
            Order,
            draft_id,
            {"status": 2, "deleted_at": timezone.now()},
            request=request,
            tenant_config=True,
        )
        return successResponse("Held cart deleted successfully.")

    @staticmethod
    def create(data, request):
        if not data.get("items"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one sale item is required.")

        with transaction.atomic():
            settings = getOptionSettings(request.user)
            shift = getCurrentRegisterContext(
                request,
                required=bool(settings.enable_cash_registers),
            )
            customer = SaleValidationService.ensureCustomer(data.get("customer_id"), request)
            order_type = SaleValidationService.ensureOrderTypeAllowed(data.get("order_type"), settings)

            sale_code = buildCode(Order, "Sale", data.get("code"), request)
            sale_order = commonQuery.createRecord(
                Order,
                {
                    "customer_id": data.get("customer_id"),
                    "register_id": shift["register_id"] if shift else None,
                    "code": sale_code,
                    "order_type": order_type,
                    "payment_status": "unpaid",
                    "discount_amount": data.get("discount_amount") or 0,
                    "discount_percentage": data.get("discount_percentage") or 0,
                    "total_coupons": data.get("total_coupons") or 0,
                    "shipping": data.get("shipping") or 0,
                    "tax_amount": data.get("tax_amount") or 0,
                    "tendered_amount": data.get("tendered_amount") or 0,
                    "note": data.get("note") or "",
                },
                request=request,
                tenant_config=True,
            )

            subtotal = Decimal("0")
            total_quantity = Decimal("0")
            total_items = 0
            sale_items = []
            for item in data.get("items") or []:
                sale_item, line_total, item_qty = SaleStockService.applySaleItem(item, sale_order, request)
                sale_items.append(sale_item)
                subtotal += line_total
                total_quantity += item_qty
                total_items += 1

            total = (
                subtotal
                - money(data.get("discount_amount"))
                + money(data.get("shipping"))
            )
            coupon_result = SaleCouponService.applyCoupons(
                sale_order,
                data.get("coupon_codes") or [],
                customer,
                data.get("items") or [],
                total,
                request,
            )
            total -= coupon_result["discount_amount"]
            payment_summary = OrderPaymentService.applyPayments(
                sale_order,
                data.get("payments") or [],
                shift,
                customer,
                settings,
                request,
            )
            paid_amount = payment_summary["paid_amount"]
            due_amount = max(total - paid_amount, Decimal("0"))
            change_amount = max(paid_amount - total, Decimal("0"))
            SaleValidationService.ensureCashChangeSupported(change_amount, payment_summary["cash_paid_amount"])
            SaleValidationService.ensurePaymentRules(
                total,
                paid_amount,
                due_amount,
                customer,
                settings,
                request,
            )

            payment_status = "paid" if due_amount == 0 else ("partially_paid" if paid_amount > 0 else "unpaid")

            if shift and change_amount > 0 and payment_summary["cash_paid_amount"] > 0:
                SaleRegisterService.recordChangeGiven(sale_order, shift, change_amount, request)

            sale_order = commonQuery.updateRecordById(
                Order,
                sale_order["id"],
                {
                    "subtotal": subtotal,
                    "total": total,
                    "tendered_amount": paid_amount,
                    "change_amount": change_amount,
                    "total_coupons": coupon_result["discount_amount"],
                    "payment_status": payment_status,
                    "final_payment_date": timezone.now() if due_amount == 0 else None,
                },
                request=request,
                tenant_config=True,
            )

            customer = SaleCustomerService.applyCustomerImpact(sale_order, request)
            reward = SaleRewardService.processRewards(sale_order, request) if settings.enable_customer_rewards else None
            AccountingService.reflectEvent(
                "order_unpaid",
                total,
                name=f"Order {sale_order['code']}",
                transaction_type="income",
                source_type="sale",
                source_id=sale_order["id"],
                transaction_date=timezone.now(),
                description=sale_order.get("note") or "Sale created",
                reference_number=sale_order["code"],
                request=request,
            )
            if paid_amount > 0:
                AccountingService.reflectEvent(
                    "order_from_unpaid_to_paid",
                    min(paid_amount, total),
                    name=f"Order payment {sale_order['code']}",
                    transaction_type="income",
                    source_type="sale",
                    source_id=sale_order["id"],
                    transaction_date=timezone.now(),
                    description="Sale payment received",
                    reference_number=sale_order["code"],
                    request=request,
                )
            cogs_amount = sum(
                (
                    money(item.get("cost_price")) * quantity(item.get("quantity"))
                    for item in sale_items
                ),
                Decimal("0"),
            )
            AccountingService.reflectEvent(
                "order_cogs",
                cogs_amount,
                name=f"Order COGS {sale_order['code']}",
                transaction_type="expense",
                source_type="sale",
                source_id=sale_order["id"],
                transaction_date=timezone.now(),
                description="Cost of goods sold",
                reference_number=sale_order["code"],
                request=request,
            )

            if data.get("draft_id"):
                draft = commonQuery.findOneRecord(
                    Order,
                    data["draft_id"],
                    request=request,
                    tenant_config=True,
                )
                if draft and draft.get("payment_status") == "hold":
                    commonQuery.updateRecordById(
                        Order,
                        draft["id"],
                        {"status": 2, "deleted_at": timezone.now()},
                        request=request,
                        tenant_config=True,
                    )

            DomainActionService.afterSaleCreated(sale_order, request)

            return successResponse(
                "Sale created successfully.",
                data={
                    **sale_order,
                    "items": sale_items,
                    "applied_coupons": coupon_result["applied_coupons"],
                    "customer": customer,
                    "reward": reward,
                    "paid_amount": paid_amount,
                },
            )

    @staticmethod
    def void(sale_order_id, data, request):
        with transaction.atomic():
            sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
            if sale_order.get("payment_status") == "void":
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Sale is already void.")
            if sale_order.get("payment_status") in ["refunded", "partially_refunded"]:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Refunded sale cannot be voided.")

            payments = commonQuery.findAllRecords(
                OrderPayment,
                {"sale_order_id": sale_order_id},
                {"attributes": ["id", "value"]},
                request=request,
                tenant_config=True,
            )
            paid_amount = sum((money(payment.get("value")) for payment in payments), Decimal("0"))
            if paid_amount > 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Paid sale cannot be voided. Use refund flow instead.")

            returns = commonQuery.findAllRecords(
                OrdersRefund,
                {"sale_order_id": sale_order_id},
                {"attributes": ["id"]},
                request=request,
                tenant_config=True,
            )
            if returns:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Returned sale cannot be voided.")

            SaleDraftService.reverseAppliedCoupons(sale_order_id, request)
            SaleDraftService.reverseRewards(sale_order, request)
            SaleVoidService.reverseCustomerImpact(sale_order, request)
            SaleVoidService.restockSale(sale_order, request)

            updated = commonQuery.updateRecordById(
                Order,
                sale_order_id,
                {
                    "payment_status": "void",
                    "note": (sale_order.get("note") or "") + (
                        f"\nVoid Note: {data.get('note')}" if data.get("note") else ""
                    ),
                },
                request=request,
                tenant_config=True,
            )
            AccountingService.reflectEvent(
                "order_unpaid_voided",
                sale_order.get("total"),
                name=f"Voided order {sale_order['code']}",
                transaction_type="adjustment",
                source_type="sale",
                source_id=sale_order_id,
                transaction_date=timezone.now(),
                description=data.get("note") or "Unpaid sale voided",
                reference_number=sale_order["code"],
                request=request,
            )
            DomainActionService.afterSaleVoided(sale_order, request)
            return successResponse("Sale voided successfully.", data=updated)

    @staticmethod
    def collectDue(sale_order_id, data, request):
        with transaction.atomic():
            sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
            if sale_order.get("payment_status") in ["void", "refunded"]:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Due cannot be collected for this sale.")

            remaining_due = saleDueAmount(sale_order)
            if remaining_due <= 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "This sale does not have any due amount.")
            if not data.get("payments"):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one payment is required.")

            settings = getOptionSettings(request.user)
            shift = getCurrentRegisterContext(
                request,
                required=bool(settings.enable_cash_registers),
            )
            customer = SaleValidationService.ensureCustomer(sale_order.get("customer_id"), request)
            payment_summary = OrderPaymentService.collectDuePayments(
                sale_order,
                data.get("payments") or [],
                shift,
                customer,
                settings,
                request,
            )
            collected_amount = payment_summary["paid_amount"]
            if collected_amount <= 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Collected amount must be greater than 0.")
            if collected_amount > remaining_due:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Collected amount cannot exceed remaining due amount.")

            next_due = max(remaining_due - collected_amount, Decimal("0"))
            next_tendered = money(sale_order.get("tendered_amount")) + collected_amount
            next_status = "paid" if next_due == 0 else "partially_paid"

            updated_sale = commonQuery.updateRecordById(
                Order,
                sale_order_id,
                {
                    "tendered_amount": next_tendered,
                    "payment_status": next_status,
                    "final_payment_date": timezone.now() if next_due == 0 else sale_order.get("final_payment_date"),
                    "note": (sale_order.get("note") or "") + (
                        f"\nDue Collection Note: {data.get('note')}" if data.get("note") else ""
                    ),
                },
                request=request,
                tenant_config=True,
            )

            if customer and collected_amount > 0:
                next_owed_amount = max(money(customer.get("owed_amount")) - collected_amount, Decimal("0"))
                commonQuery.updateRecordById(
                    Customer,
                    customer["id"],
                    {"owed_amount": next_owed_amount},
                    request=request,
                    tenant_config=True,
                )
                commonQuery.createRecord(
                    CustomerAccountHistory,
                    {
                        "customer_id": customer["id"],
                        "amount": collected_amount,
                        "previous_amount": customer.get("owed_amount"),
                        "next_amount": next_owed_amount,
                        "operation": "payment",
                        "order_id": sale_order_id,
                        "description": data.get("note") or f"Due collected for sale {sale_order['code']}",
                    },
                    request=request,
                    tenant_config=True,
                )

            AccountingService.reflectEvent(
                "order_from_unpaid_to_paid",
                collected_amount,
                name=f"Due collection {sale_order['code']}",
                transaction_type="income",
                source_type="sale",
                source_id=sale_order_id,
                transaction_date=timezone.now(),
                description=data.get("note") or "Sale due collected",
                reference_number=sale_order["code"],
                request=request,
            )
            refreshed_sale = SaleService.buildSaleDetail(sale_order_id, request)
            return successResponse(
                "Due collected successfully.",
                data={
                    **refreshed_sale,
                    "collected_amount": collected_amount,
                },
            )

    @staticmethod
    def updateProcessingStatus(sale_order_id, data, request):
        sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        updated = commonQuery.updateRecordById(
            Order,
            sale_order_id,
            {
                "process_status": data.get("status") or "",
                "note": data.get("note") or sale_order.get("note") or "",
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Processing status updated successfully.", data=updated)

    @staticmethod
    def updateDeliveryStatus(sale_order_id, data, request):
        sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        updated = commonQuery.updateRecordById(
            Order,
            sale_order_id,
            {
                "delivery_status": data.get("status") or "",
                "note": data.get("note") or sale_order.get("note") or "",
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Delivery status updated successfully.", data=updated)

    @staticmethod
    def getInstallments(sale_order_id, request):
        SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        sale_data = SaleService.buildSaleDetail(sale_order_id, request)
        return successResponse("Instalments retrieved successfully.", data=sale_data.get("instalments"))

    @staticmethod
    def createInstallments(sale_order_id, data, request):
        sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        lines = data.get("lines") or []
        if not lines:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one installment line is required.")
        if saleDueAmount(sale_order) <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Installments can be created only when due amount exists.")

        with transaction.atomic():
            OrderInstalment.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                sale_order_id=sale_order_id,
            ).delete()

            for line in lines:
                commonQuery.createRecord(
                    OrderInstalment,
                    {
                        "sale_order_id": sale_order_id,
                        "date": line.get("date") or line.get("due_date"),
                        "amount": line.get("amount") or 0,
                        "paid": False,
                    },
                    request=request,
                    tenant_config=True,
                )

            commonQuery.updateRecordById(
                Order,
                sale_order_id,
                {
                    "support_instalments": True,
                    "total_instalments": data.get("total_installments") or len(lines),
                    "final_payment_date": data.get("final_payment_date") or None,
                },
                request=request,
                tenant_config=True,
            )
            sale_data = SaleService.buildSaleDetail(sale_order_id, request)
            return successResponse("Instalments saved successfully.", data=sale_data.get("instalments"))

    @staticmethod
    def updateInstallment(sale_order_id, installment_id, data, request):
        SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        installment = commonQuery.findOneRecord(
            OrderInstalment,
            {"id": installment_id, "sale_order_id": sale_order_id},
            request=request,
            tenant_config=True,
        )
        if installment is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Installment not found.")
        update_data = dict(data or {})
        if "due_date" in update_data:
            update_data["date"] = update_data.pop("due_date")
        updated = commonQuery.updateRecordById(
            OrderInstalment,
            installment_id,
            update_data,
            request=request,
            tenant_config=True,
        )
        return successResponse("Installment updated successfully.", data=updated)

    @staticmethod
    def deleteInstallment(sale_order_id, installment_id, request):
        SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        installment = commonQuery.findOneRecord(
            OrderInstalment,
            {"id": installment_id, "sale_order_id": sale_order_id},
            request=request,
            tenant_config=True,
        )
        if installment is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Installment not found.")
        if installment.get("paid"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Paid installment cannot be deleted.")
        OrderInstalment.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            id=installment_id,
            sale_order_id=sale_order_id,
        ).delete()
        return successResponse("Installment deleted successfully.")

    @staticmethod
    def payInstallment(sale_order_id, installment_id, data, request):
        sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        installment = commonQuery.findOneRecord(
            OrderInstalment,
            {"id": installment_id, "sale_order_id": sale_order_id},
            request=request,
            tenant_config=True,
        )
        if installment is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Installment not found.")
        if installment.get("paid"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Installment is already paid.")

        amount = money(data.get("amount"))
        if amount <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Installment amount must be greater than 0.")
        if amount != money(installment.get("amount")):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Installment payment must match the installment amount.")

        with transaction.atomic():
            settings = getOptionSettings(request.user)
            shift = getCurrentRegisterContext(
                request,
                required=bool(settings.enable_cash_registers),
            )
            customer = SaleValidationService.ensureCustomer(sale_order.get("customer_id"), request)
            payment_summary = OrderPaymentService.collectDuePayments(
                sale_order,
                [
                    {
                        "payment_type": data.get("payment_type") or "cash-payment",
                        "amount": amount,
                        "reference_number": data.get("reference_number") or "",
                        "note": data.get("note") or f"Installment #{installment_id} payment",
                    }
                ],
                shift,
                customer,
                settings,
                request,
            )

            commonQuery.updateRecordById(
                OrderInstalment,
                installment_id,
                {
                    "paid": True,
                    "payment_id": (payment_summary.get("payment_ids") or [None])[0],
                },
                request=request,
                tenant_config=True,
            )

            next_due = max(saleDueAmount(sale_order) - amount, Decimal("0"))
            next_tendered = money(sale_order.get("tendered_amount")) + amount
            commonQuery.updateRecordById(
                Order,
                sale_order_id,
                {
                    "tendered_amount": next_tendered,
                    "payment_status": "paid" if next_due == 0 else "partially_paid",
                    "final_payment_date": timezone.now() if next_due == 0 else sale_order.get("final_payment_date"),
                },
                request=request,
                tenant_config=True,
            )
            if customer:
                next_owed_amount = max(money(customer.get("owed_amount")) - amount, Decimal("0"))
                commonQuery.updateRecordById(
                    Customer,
                    customer["id"],
                    {"owed_amount": next_owed_amount},
                    request=request,
                    tenant_config=True,
                )
                commonQuery.createRecord(
                    CustomerAccountHistory,
                    {
                        "customer_id": customer["id"],
                        "amount": amount,
                        "previous_amount": customer.get("owed_amount"),
                        "next_amount": next_owed_amount,
                        "operation": "payment",
                        "order_id": sale_order_id,
                        "description": data.get("note") or f"Installment payment for sale {sale_order['code']}",
                    },
                    request=request,
                    tenant_config=True,
                )

            AccountingService.reflectEvent(
                "order_from_unpaid_to_paid",
                amount,
                name=f"Installment payment {sale_order['code']}",
                transaction_type="income",
                source_type="sale",
                source_id=sale_order_id,
                transaction_date=timezone.now(),
                description=data.get("note") or "Sale installment payment",
                reference_number=sale_order["code"],
                request=request,
            )
            refreshed_sale = SaleService.buildSaleDetail(sale_order_id, request)
            return successResponse("Installment paid successfully.", data=refreshed_sale)

    @staticmethod
    def createReturn(sale_order_id, data, request):
        SaleReturnValidationService.ensureReturnType(data.get("return_type") or "refund")

        with transaction.atomic():
            sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
            settings = getOptionSettings(request.user)
            customer = SaleValidationService.ensureCustomer(sale_order.get("customer_id"), request) if sale_order.get("customer_id") else None
            prepared = SaleReturnValidationService.validateItems(sale_order, data.get("items") or [], request)

            return_order = commonQuery.createRecord(
                OrdersRefund,
                {
                    "sale_order_id": sale_order["id"],
                    "tax_amount": prepared["tax_amount"],
                    "shipping": 0,
                    "total": prepared["total"],
                    "payment_method": data.get("payment_type") or "",
                },
                request=request,
                tenant_config=True,
            )

            created_items = []
            for item in prepared["items"]:
                return_item = commonQuery.createRecord(
                    OrdersProductsRefund,
                    {
                        "return_order_id": return_order["id"],
                        "sale_order_id": sale_order["id"],
                        "sale_item_id": item["sale_item"]["id"],
                        "product_id": item["sale_item"].get("product_id"),
                        "unit_id": item["sale_item"].get("unit_id"),
                        "quantity": item["quantity"],
                        "unit_price": item["unit_price"],
                        "tax_amount": item["tax_amount"],
                        "total": item["line_total"] + item["tax_amount"],
                        "condition": item["condition"],
                        "description": item["note"],
                    },
                    request=request,
                    tenant_config=True,
                )
                created_items.append(return_item)

                refunded_qty = SaleReturnValidationService.refundedQuantity(item["sale_item"]["id"], request)
                item_status = "returned" if refunded_qty >= quantity(item["sale_item"].get("quantity")) else "partially_returned"
                commonQuery.updateRecordById(
                    OrdersProduct,
                    item["sale_item"]["id"],
                    {"item_status": item_status},
                    request=request,
                    tenant_config=True,
                )
                SaleRefundService.restoreStock(return_order, item, request)

            settlement = SaleRefundService.handleRefundSettlement(
                return_order,
                sale_order,
                customer,
                data,
                prepared["total"],
                settings,
                request,
            )
            updated_sale = SaleRefundService.updateOrderPaymentStatus(sale_order["id"], request)
            AccountingService.reflectEvent(
                "order_refunded",
                prepared["total"],
                name=f"Order refund {sale_order['code']}",
                transaction_type="adjustment",
                source_type="sale",
                source_id=sale_order["id"],
                transaction_date=timezone.now(),
                description=data.get("note") or "Sale refunded",
                reference_number=sale_order["code"],
                request=request,
            )
            DomainActionService.afterSaleRefunded(sale_order, return_order, request)

            return successResponse(
                "Sale return processed successfully.",
                data={
                    "return_order": return_order,
                    "items": created_items,
                    "refund_payment": settlement["refund_payment"],
                    "difference_amount": settlement["difference_amount"],
                    "sale_order": updated_sale,
                },
            )

    @staticmethod
    def getRefunds(sale_order_id, request):
        SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        refunds = commonQuery.findAllRecords(
            OrdersRefund,
            {"sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "sale_order_id",
                    "sale_order__customer_id",
                    "user_id",
                    "user__full_name",
                    "tax_amount",
                    "shipping",
                    "total",
                    "payment_method",
                    "created_at",
                ],
                "order": ["-id"],
            },
            request=request,
            tenant_config=True,
        )
        for refund in refunds:
            refund["items"] = commonQuery.findAllRecords(
                OrdersProductsRefund,
                {"return_order_id": refund["id"]},
                {
                    "attributes": [
                        "id",
                        "sale_item_id",
                        "sale_item__product__name",
                        "quantity",
                        "unit_price",
                        "tax_amount",
                        "total",
                        "condition",
                        "description",
                    ],
                },
                request=request,
                tenant_config=True,
            )
        return successResponse("Sale refunds retrieved successfully.", data=refunds)

    @staticmethod
    def getRefundedItems(sale_order_id, request):
        SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        refunded_items = commonQuery.findAllRecords(
            OrdersProductsRefund,
            {"return_order__sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "return_order_id",
                    "sale_item_id",
                    "sale_item__product__name",
                    "quantity",
                    "unit_price",
                    "tax_amount",
                    "total",
                    "condition",
                    "description",
                    "created_at",
                ],
                "order": ["-id"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Refunded sale items retrieved successfully.", data=refunded_items)
