# type: ignore
import json
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import Product, ProductUnitQuantity
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode, jsonsafe
from apps.common.responses import successResponse
from apps.customers.models import Customer, CustomerAccountHistory, CustomerCreditLedger, CustomerWalletTransaction
from apps.inventory.models import StockLedger
from apps.payments.models import RefundPayment, SalePayment
from apps.payments.services import PaymentTypeService
from apps.promotions.models import AppliedCoupon, Coupon, CouponCategory, CouponCustomer, CouponCustomerGroup, CouponProduct, CustomerCoupon
from apps.registers.models import CashierShift, CashRegisterEntry
from apps.rewards.services import CustomerRewardService
from apps.sales.models import (
    CartDraft,
    ExchangeOrderLink,
    InstallmentLine,
    InstallmentPlan,
    ReturnItem,
    ReturnOrder,
    SaleItem,
    SaleOrder,
)
from apps.settingsapi.services import BusinessSettingService


def money(value):
    return Decimal(str(value or 0))


def quantity(value):
    return Decimal(str(value or 0))


def getBusinessSettings(user):
    return BusinessSettingService.ensureSettings(user)


def getCurrentShift(request, shift_id=None, required=True):
    where = {"id": shift_id} if shift_id else {"cashier_id": request.user.id, "shift_status": "open"}
    shift = commonQuery.findOneRecord(
        CashierShift,
        where,
        request=request,
        tenant_config=True,
    )
    if shift is None or shift.get("shift_status") != "open":
        if not required:
            return None
        raise api_error(400, ErrorCodes.BAD_REQUEST, "Open cashier shift is required to create sale.")
    return shift


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
        stock_qty = item_qty
        unit_id = item.get("unit_id") or product.get("unit_id")
        default_unit_price = product.get("selling_price")
        default_purchase_price = product.get("purchase_price")
        if item.get("unit_quantity_id"):
            unit_quantity = commonQuery.findOneRecord(
                ProductUnitQuantity,
                {"id": item.get("unit_quantity_id"), "product_id": product["id"]},
                request=request,
                tenant_config=True,
            )
            if unit_quantity is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product selling unit not found.")
            unit_id = unit_quantity.get("unit_id") or unit_id
            stock_qty = item_qty * quantity(unit_quantity.get("quantity") or 1)
            default_unit_price = unit_quantity.get("sale_price") or default_unit_price
            default_purchase_price = unit_quantity.get("purchase_price") or default_purchase_price

        unit_price = money(item.get("unit_price") if item.get("unit_price") is not None else default_unit_price)
        discount_amount = money(item.get("discount_amount"))
        tax_amount = money(item.get("tax_amount"))
        line_total = (item_qty * unit_price) - discount_amount + tax_amount

        sale_item = commonQuery.createRecord(
            SaleItem,
            {
                "sale_order_id": sale_order["id"],
                "product_id": product["id"],
                "unit_id": unit_id,
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

        if product.get("track_stock") and product.get("product_type") == "stock":
            available_stock = quantity(product.get("current_stock"))
            if available_stock < stock_qty:
                raise api_error(400, ErrorCodes.BAD_REQUEST, f"Insufficient stock for {product.get('name')}.")
            new_balance = available_stock - stock_qty
            Product.objects.filter(id=product["id"]).update(current_stock=F("current_stock") - stock_qty)
            commonQuery.createRecord(
                StockLedger,
                {
                    "product_id": product["id"],
                    "entry_type": "sale",
                    "quantity": stock_qty * Decimal("-1"),
                    "unit_cost": default_purchase_price or 0,
                    "balance_after": new_balance,
                    "reference_type": "sale_order",
                    "reference_id": sale_order["id"],
                    "note": f"Sale {sale_order['code']}",
                },
                request=request,
                tenant_config=True,
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
    def ensurePaymentRules(total, paid_amount, due_amount, customer, settings):
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


class SaleRegisterService:
    @staticmethod
    def recordCashSalePayment(sale_order, sale_payment, shift, amount, request):
        balance_before = money(shift.get("expected_cash"))
        balance_after = balance_before + amount
        CashierShift.objects.filter(id=shift["id"]).update(expected_cash=F("expected_cash") + amount)
        shift["expected_cash"] = balance_after
        commonQuery.createRecord(
            CashRegisterEntry,
            {
                "shift_id": shift["id"],
                "register_id": shift["register_id"],
                "cashier_id": request.user.id,
                "payment_type": "cash-payment",
                "entry_type": "sale_payment",
                "amount": amount,
                "balance_before": balance_before,
                "balance_after": balance_after,
                "reference_type": "sale_payment",
                "reference_id": sale_payment["id"],
                "note": f"Sale payment for {sale_order['code']}",
            },
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def recordChangeGiven(sale_order, shift, change_amount, request):
        balance_before = money(shift.get("expected_cash"))
        balance_after = balance_before - change_amount
        CashierShift.objects.filter(id=shift["id"]).update(expected_cash=F("expected_cash") - change_amount)
        shift["expected_cash"] = balance_after
        commonQuery.createRecord(
            CashRegisterEntry,
            {
                "shift_id": shift["id"],
                "register_id": shift["register_id"],
                "cashier_id": request.user.id,
                "payment_type": "cash-payment",
                "entry_type": "change_given",
                "amount": change_amount,
                "balance_before": balance_before,
                "balance_after": balance_after,
                "reference_type": "sale_order",
                "reference_id": sale_order["id"],
                "note": f"Change given for sale {sale_order['code']}",
            },
            request=request,
            tenant_config=True,
        )


class SaleCustomerAccountService:
    @staticmethod
    def applyAccountPayment(customer, sale_order, amount, payment_note, request):
        balance_before = money(customer.get("wallet_balance"))
        if balance_before < amount:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer account balance is not enough for this payment.")
        balance_after = balance_before - amount
        Customer.objects.filter(id=customer["id"]).update(wallet_balance=balance_after)
        customer["wallet_balance"] = balance_after
        commonQuery.createRecord(
            CustomerAccountHistory,
            {
                "customer_id": customer["id"],
                "amount": amount,
                "action": "debit",
                "balance_before": balance_before,
                "balance_after": balance_after,
                "reference_type": "sale_order",
                "reference_id": sale_order["id"],
                "note": payment_note or f"Sale payment for {sale_order['code']}",
            },
            request=request,
            tenant_config=True,
        )
        commonQuery.createRecord(
            CustomerWalletTransaction,
            {
                "customer_id": customer["id"],
                "entry_type": "payment",
                "amount": amount,
                "balance_after": balance_after,
                "note": payment_note or f"Sale payment for {sale_order['code']}",
                "reference_type": "sale_order",
                "reference_id": sale_order["id"],
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

        product_ids = [item.get("product_id") for item in items or []]
        category_ids = []
        for product_id in product_ids:
            product = commonQuery.findOneRecord(Product, product_id, request=request, tenant_config=True)
            if product and product.get("category_id"):
                category_ids.append(product["category_id"])

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
                "code": coupon["code"],
                "expires_at": coupon.get("valid_until"),
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
                if issued_coupon.get("is_redeemed"):
                    raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {code} is already redeemed.")
                if issued_coupon.get("expires_at") and timezone.localtime() > issued_coupon["expires_at"]:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, f"Coupon {code} has expired.")
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
                AppliedCoupon,
                {
                    "sale_order_id": sale_order["id"],
                    "coupon_id": coupon["id"],
                    "customer_coupon_id": issued_coupon["id"] if issued_coupon else None,
                    "code": code,
                    "type": coupon["type"],
                    "discount_value": coupon["discount_value"],
                    "discount_amount": discount_amount,
                },
                request=request,
                tenant_config=True,
            )

            if issued_coupon:
                usage_count = int(issued_coupon.get("usage_count") or 0) + 1
                update_data = {"usage_count": usage_count}
                limit_usage = int(coupon.get("limit_usage") or 0)
                if limit_usage > 0 and usage_count >= limit_usage:
                    update_data["is_redeemed"] = True
                    update_data["redeemed_at"] = timezone.now()
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


class SalePaymentService:
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

            sale_payment = commonQuery.createRecord(
                SalePayment,
                {
                    "sale_order_id": sale_order["id"],
                    "payment_type": payment_type,
                    "shift_id": shift["id"] if shift else None,
                    "amount": amount,
                    "paid_at": timezone.now(),
                    "reference_number": payment.get("reference_number") or "",
                    "note": payment.get("note") or "",
                },
                request=request,
                tenant_config=True,
            )
            paid_amount += amount

            if payment_type == "cash-payment" and shift:
                cash_paid_amount += amount
                SaleRegisterService.recordCashSalePayment(sale_order, sale_payment, shift, amount, request)
            elif payment_type == "account-payment":
                SaleCustomerAccountService.applyAccountPayment(customer, sale_order, amount, payment.get("note"), request)

        if shift:
            CashierShift.objects.filter(id=shift["id"]).update(total_sales_amount=F("total_sales_amount") + sale_order["total"])
        return {
            "paid_amount": paid_amount,
            "cash_paid_amount": cash_paid_amount,
        }

    @staticmethod
    def collectDuePayments(sale_order, payments, shift, customer, settings, request):
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

            sale_payment = commonQuery.createRecord(
                SalePayment,
                {
                    "sale_order_id": sale_order["id"],
                    "payment_type": payment_type,
                    "shift_id": shift["id"] if shift else None,
                    "amount": amount,
                    "paid_at": timezone.now(),
                    "reference_number": payment.get("reference_number") or "",
                    "note": payment.get("note") or payment.get("reference_number") or "",
                },
                request=request,
                tenant_config=True,
            )
            paid_amount += amount

            if payment_type == "cash-payment" and shift:
                cash_paid_amount += amount
                SaleRegisterService.recordCashSalePayment(sale_order, sale_payment, shift, amount, request)
            elif payment_type == "account-payment":
                SaleCustomerAccountService.applyAccountPayment(customer, sale_order, amount, payment.get("note"), request)

        return {
            "paid_amount": paid_amount,
            "cash_paid_amount": cash_paid_amount,
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

        Customer.objects.filter(id=customer_id).update(
            total_sales=F("total_sales") + sale_order["total"],
            total_sales_count=F("total_sales_count") + 1,
            owed_amount=F("owed_amount") + sale_order["due_amount"],
        )

        if money(sale_order.get("due_amount")) > 0:
            balance_after = money(customer_before.get("owed_amount") if customer_before else 0) + money(sale_order["due_amount"])
            commonQuery.createRecord(
                CustomerCreditLedger,
                {
                    "customer_id": customer_id,
                    "amount": sale_order["due_amount"],
                    "direction": "increase",
                    "balance_after": balance_after,
                    "reason": "sale_due",
                    "reference_type": "sale_order",
                    "reference_id": sale_order["id"],
                    "note": f"Due created for sale {sale_order['code']}",
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

            unit_price = money(
                item.get("unit_price")
                if item.get("unit_price") is not None
                else product.get("selling_price")
            )
            unit_id = item.get("unit_id") or product.get("unit_id")
            unit_quantity_id = item.get("unit_quantity_id")
            if unit_quantity_id:
                unit_quantity = commonQuery.findOneRecord(
                    ProductUnitQuantity,
                    {"id": unit_quantity_id, "product_id": product["id"]},
                    request=request,
                    tenant_config=True,
                )
                if unit_quantity is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Product selling unit not found.")
                unit_id = unit_quantity.get("unit_id") or unit_id
                if item.get("unit_price") is None:
                    unit_price = money(unit_quantity.get("sale_price") or product.get("selling_price"))
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
        total_quantity = sum([quantity(item.get("quantity")) for item in items], Decimal("0"))
        return {
            **draft,
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
            AppliedCoupon,
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
            usage_count = max(int(issued_coupon.get("usage_count") or 0) - 1, 0)
            update_data = {"usage_count": usage_count}
            if issued_coupon.get("is_redeemed") and coupon:
                limit_usage = int(coupon.get("limit_usage") or 0)
                if limit_usage <= 0 or usage_count < limit_usage:
                    update_data["is_redeemed"] = False
                    update_data["redeemed_at"] = None
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

        from apps.rewards.models import CustomerRewardBalance, RewardRedemption
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
        earned_points = int(rule.get("reward") or 0) if rule else 0
        sale_note = f"Reward earned from sale {sale_order['code']}."

        redemptions = commonQuery.findAllRecords(
            RewardRedemption,
            {
                "customer_id": customer_id,
                "reward_system_id": reward_system["id"],
                "note": sale_note,
            },
            {
                "attributes": [
                    "id",
                    "customer_coupon_id",
                    "points_redeemed",
                ],
            },
            request=request,
            tenant_config=True,
        )

        restored_points = sum(
            [int(redemption.get("points_redeemed") or 0) for redemption in redemptions],
            0,
        )
        customer_coupon_ids = [
            redemption["customer_coupon_id"]
            for redemption in redemptions
            if redemption.get("customer_coupon_id")
        ]

        balance = commonQuery.findOneRecord(
            CustomerRewardBalance,
            {"customer_id": customer_id, "reward_system_id": reward_system["id"]},
            request=request,
            tenant_config=True,
        )
        if balance is None:
            return

        next_points = max(int(balance.get("points") or 0) + restored_points - earned_points, 0)
        next_lifetime = max(int(balance.get("lifetime_points") or 0) - earned_points, 0)

        commonQuery.updateRecordById(
            CustomerRewardBalance,
            balance["id"],
            {
                "points": next_points,
                "lifetime_points": next_lifetime,
            },
            request=request,
            tenant_config=True,
        )

        for customer_coupon_id in customer_coupon_ids:
            commonQuery.updateRecordById(
                CustomerCoupon,
                customer_coupon_id,
                {"status": 2, "deleted_at": timezone.now()},
                request=request,
                tenant_config=True,
            )

        for redemption in redemptions:
            commonQuery.updateRecordById(
                RewardRedemption,
                redemption["id"],
                {"status": 2, "deleted_at": timezone.now()},
                request=request,
                tenant_config=True,
            )


class SaleVoidService:
    @staticmethod
    def restockSale(sale_order, request):
        items = commonQuery.findAllRecords(
            SaleItem,
            {"sale_order_id": sale_order["id"]},
            {
                "attributes": [
                    "id",
                    "product_id",
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
            if not product or not product.get("track_stock") or product.get("product_type") != "stock":
                continue
            restock_qty = quantity(item.get("quantity"))
            new_balance = quantity(product.get("current_stock")) + restock_qty
            Product.objects.filter(id=product["id"]).update(current_stock=F("current_stock") + restock_qty)
            commonQuery.createRecord(
                StockLedger,
                {
                    "product_id": product["id"],
                    "entry_type": "sale_return",
                    "quantity": restock_qty,
                    "unit_cost": item.get("cost_price") or product.get("purchase_price") or 0,
                    "balance_after": new_balance,
                    "reference_type": "sale_void",
                    "reference_id": sale_order["id"],
                    "note": f"Void sale {sale_order['code']}",
                },
                request=request,
                tenant_config=True,
            )
            commonQuery.updateRecordById(
                SaleItem,
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

        due_amount = money(sale_order.get("due_amount"))
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
                CustomerCreditLedger,
                {
                    "customer_id": customer_id,
                    "amount": due_amount,
                    "direction": "decrease",
                    "balance_after": next_owed_amount,
                    "reason": "sale_void",
                    "reference_type": "sale_order",
                    "reference_id": sale_order["id"],
                    "note": f"Due reversed for void sale {sale_order['code']}",
                },
                request=request,
                tenant_config=True,
            )


class SaleReturnValidationService:
    @staticmethod
    def ensureSaleOrder(sale_order_id, request):
        sale_order = commonQuery.findOneRecord(
            SaleOrder,
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
            SaleItem,
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
            ReturnItem,
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
                    "condition": item.get("condition") or "good",
                    "note": item.get("note") or "",
                }
            )

        previous_returns = commonQuery.findAllRecords(
            ReturnOrder,
            {"sale_order_id": sale_order["id"]},
            {"attributes": ["total"]},
            request=request,
            tenant_config=True,
        )
        already_refunded_total = sum([money(return_row.get("total")) for return_row in previous_returns], Decimal("0"))
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
    def updateSalePaymentStatus(sale_order_id, request):
        sale_order = commonQuery.findOneRecord(SaleOrder, sale_order_id, request=request, tenant_config=True)
        if sale_order is None:
            return None
        returns = commonQuery.findAllRecords(
            ReturnOrder,
            {"sale_order_id": sale_order_id},
            {"attributes": ["total"]},
            request=request,
            tenant_config=True,
        )
        refunded_total = sum([money(row.get("total")) for row in returns], Decimal("0"))
        sale_total = money(sale_order.get("total"))
        status = sale_order.get("payment_status")
        if refunded_total <= 0:
            return sale_order
        status = "refunded" if refunded_total >= sale_total else "partially_refunded"
        return commonQuery.updateRecordById(
            SaleOrder,
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
        if not product or not product.get("track_stock") or product.get("product_type") != "stock":
            return

        refund_qty = prepared_item["quantity"]
        current_stock = quantity(product.get("current_stock"))
        returned_balance = current_stock + refund_qty
        Product.objects.filter(id=product["id"]).update(current_stock=F("current_stock") + refund_qty)
        commonQuery.createRecord(
            StockLedger,
            {
                "product_id": product["id"],
                "entry_type": "sale_return",
                "quantity": refund_qty,
                "unit_cost": sale_item.get("cost_price") or product.get("purchase_price") or 0,
                "balance_after": returned_balance,
                "reference_type": "return_order",
                "reference_id": return_order["id"],
                "note": f"Sale return {return_order['id']}",
            },
            request=request,
            tenant_config=True,
        )

        if prepared_item["condition"] == "damaged":
            damaged_balance = returned_balance - refund_qty
            Product.objects.filter(id=product["id"]).update(current_stock=F("current_stock") - refund_qty)
            commonQuery.createRecord(
                StockLedger,
                {
                    "product_id": product["id"],
                    "entry_type": "adjustment_out",
                    "quantity": refund_qty * Decimal("-1"),
                    "unit_cost": sale_item.get("cost_price") or product.get("purchase_price") or 0,
                    "balance_after": damaged_balance,
                    "reference_type": "return_order",
                    "reference_id": return_order["id"],
                    "note": f"Damaged return {return_order['id']}",
                },
                request=request,
                tenant_config=True,
            )

    @staticmethod
    def creditCustomerAccount(customer, sale_order, amount, note, request):
        balance_before = money(customer.get("wallet_balance"))
        balance_after = balance_before + amount
        Customer.objects.filter(id=customer["id"]).update(wallet_balance=balance_after)
        commonQuery.createRecord(
            CustomerAccountHistory,
            {
                "customer_id": customer["id"],
                "amount": amount,
                "action": "credit",
                "balance_before": balance_before,
                "balance_after": balance_after,
                "reference_type": "sale_return",
                "reference_id": sale_order["id"],
                "note": note or f"Refund for sale {sale_order['code']}",
            },
            request=request,
            tenant_config=True,
        )
        commonQuery.createRecord(
            CustomerWalletTransaction,
            {
                "customer_id": customer["id"],
                "entry_type": "refund",
                "amount": amount,
                "balance_after": balance_after,
                "reference_type": "sale_return",
                "reference_id": sale_order["id"],
                "note": note or f"Refund for sale {sale_order['code']}",
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
                    SaleOrder,
                    data["exchange_sale_id"],
                    request=request,
                    tenant_config=True,
                )
                if exchange_sale is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Exchange sale not found.")
                difference_amount = money(exchange_sale.get("total")) - total
                commonQuery.createRecord(
                    ExchangeOrderLink,
                    {
                        "return_order_id": return_order["id"],
                        "new_sale_order_id": exchange_sale["id"],
                        "difference_amount": difference_amount,
                    },
                    request=request,
                    tenant_config=True,
                )
                if difference_amount < 0 and data.get("payment_type"):
                    total_to_refund = abs(difference_amount)
                    payment_data = {**data, "return_type": "refund"}
                    settlement = SaleRefundService.handleRefundSettlement(return_order, sale_order, customer, payment_data, total_to_refund, settings, request)
                    return {"refund_payment": settlement["refund_payment"], "difference_amount": difference_amount}
            return {"refund_payment": None, "difference_amount": difference_amount}

        payment_type = PaymentTypeService.resolvePaymentType(data.get("payment_type"), request)
        shift = getCurrentShift(request, data.get("shift_id"), required=bool(settings.enable_cash_registers and payment_type == "cash-payment"))
        refund_payment = commonQuery.createRecord(
            RefundPayment,
            {
                "return_order_id": return_order["id"],
                "payment_type": payment_type,
                "shift_id": shift["id"] if shift else None,
                "amount": total,
                "refunded_at": timezone.now(),
                "reference_number": data.get("reference_number") or "",
                "note": data.get("note") or "",
            },
            request=request,
            tenant_config=True,
        )

        if payment_type == "cash-payment" and shift:
            balance_before = money(shift.get("expected_cash"))
            balance_after = balance_before - total
            CashierShift.objects.filter(id=shift["id"]).update(
                expected_cash=F("expected_cash") - total,
                total_refund_amount=F("total_refund_amount") + total,
            )
            commonQuery.createRecord(
                CashRegisterEntry,
                {
                    "shift_id": shift["id"],
                    "register_id": shift["register_id"],
                    "cashier_id": request.user.id,
                    "payment_type": payment_type,
                    "entry_type": "refund",
                    "amount": total,
                    "balance_before": balance_before,
                    "balance_after": balance_after,
                    "reference_type": "refund_payment",
                    "reference_id": refund_payment["id"],
                    "note": data.get("note") or f"Refund for sale {sale_order['code']}",
                },
                request=request,
                tenant_config=True,
            )
        elif payment_type == "account-payment":
            if not settings.enable_credit_account:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer credit account is disabled.")
            if not customer:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer is required for account refund.")
            SaleRefundService.creditCustomerAccount(customer, sale_order, total, data.get("note"), request)

        return {"refund_payment": refund_payment, "difference_amount": Decimal("0")}


class SaleService:
    @staticmethod
    def listSales(data, request):
        field_config = [
            ["code", True, True],
            ["payment_status", True, True],
            ["order_type", True, True],
            ["customer__name", True, False],
            ["cashier__full_name", True, False],
        ]
        result = commonQuery.fetchPaginatedData(
            SaleOrder,
            data,
            field_config,
            {
                "attributes": [
                    "id",
                    "code",
                    "customer_id",
                    "customer__name",
                    "cashier_id",
                    "cashier__full_name",
                    "register_id",
                    "register__name",
                    "shift_id",
                    "order_type",
                    "payment_status",
                    "subtotal",
                    "discount_amount",
                    "coupon_discount_amount",
                    "shipping_amount",
                    "tax_amount",
                    "total",
                    "tendered_amount",
                    "change_amount",
                    "due_amount",
                    "total_items",
                    "total_quantity",
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
            SaleOrder,
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
            SaleItem,
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

        payments = commonQuery.findAllRecords(
            SalePayment,
            {"sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "payment_type",
                    "shift_id",
                    "amount",
                    "paid_at",
                    "reference_number",
                    "note",
                ],
                "order": ["id"],
            },
            request=request,
            tenant_config=True,
        )

        applied_coupons = commonQuery.findAllRecords(
            AppliedCoupon,
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
            ReturnOrder,
            {"sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "customer_id",
                    "cashier_id",
                    "cashier__full_name",
                    "return_type",
                    "return_status",
                    "subtotal",
                    "tax_amount",
                    "total",
                    "note",
                    "created_at",
                ],
                "order": ["-id"],
            },
            request=request,
            tenant_config=True,
        )
        for refund in refunds:
            refund["items"] = commonQuery.findAllRecords(
                ReturnItem,
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
            refund["payments"] = commonQuery.findAllRecords(
                RefundPayment,
                {"return_order_id": refund["id"]},
                {
                    "attributes": [
                        "id",
                        "payment_type",
                        "shift_id",
                        "amount",
                        "refunded_at",
                        "reference_number",
                        "note",
                    ],
                    "order": ["id"],
                },
                request=request,
                tenant_config=True,
            )

        totals = {
            "paid_amount": sum([money(payment.get("amount")) for payment in payments], Decimal("0")),
            "refunded_amount": sum([money(refund.get("total")) for refund in refunds], Decimal("0")),
        }

        installment_plan = commonQuery.findOneRecord(
            InstallmentPlan,
            {"sale_order_id": sale_order_id},
            request=request,
            tenant_config=True,
        )
        if installment_plan:
            installment_plan["lines"] = commonQuery.findAllRecords(
                InstallmentLine,
                {"plan_id": installment_plan["id"]},
                {
                    "attributes": [
                        "id",
                        "due_date",
                        "amount",
                        "paid_amount",
                        "installment_status",
                        "created_at",
                    ],
                    "order": ["due_date", "id"],
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
            "installment_plan": installment_plan,
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
            "cashier_id": sale_data.get("cashier_id"),
            "register_id": sale_data.get("register_id"),
            "subtotal": sale_data.get("subtotal"),
            "discount_amount": sale_data.get("discount_amount"),
            "coupon_discount_amount": sale_data.get("coupon_discount_amount"),
            "shipping_amount": sale_data.get("shipping_amount"),
            "tax_amount": sale_data.get("tax_amount"),
            "total": sale_data.get("total"),
            "tendered_amount": sale_data.get("tendered_amount"),
            "change_amount": sale_data.get("change_amount"),
            "due_amount": sale_data.get("due_amount"),
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
            CartDraft,
            {
                "customer_id": customer["id"] if customer else None,
                "cashier_id": request.user.id,
                "code": buildCode(CartDraft, "hold-cart", data.get("code"), request),
                "draft_status": "held",
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
        filter_data["draft_status"] = "held"
        filters["filter"] = filter_data
        result = commonQuery.fetchPaginatedData(
            CartDraft,
            filters,
            [["code", True, True], ["customer__name", True, False], ["cashier__full_name", True, False]],
            {
                "attributes": [
                    "id",
                    "code",
                    "customer_id",
                    "customer__name",
                    "cashier_id",
                    "cashier__full_name",
                    "draft_status",
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
            CartDraft,
            draft_id,
            request=request,
            tenant_config=True,
        )
        if draft is None or draft.get("draft_status") != "held":
            raise api_error(404, ErrorCodes.NOT_FOUND, "Held cart not found.")
        return successResponse(
            "Held cart retrieved successfully.",
            data=SaleDraftService.buildDraftData(draft, request),
        )

    @staticmethod
    def deleteHeldCart(draft_id, request):
        draft = commonQuery.findOneRecord(
            CartDraft,
            draft_id,
            request=request,
            tenant_config=True,
        )
        if draft is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Held cart not found.")
        commonQuery.updateRecordById(
            CartDraft,
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
            settings = getBusinessSettings(request.user)
            shift = getCurrentShift(
                request,
                data.get("shift_id"),
                required=bool(settings.enable_cash_registers),
            )
            customer = SaleValidationService.ensureCustomer(data.get("customer_id"), request)
            order_type = SaleValidationService.ensureOrderTypeAllowed(data.get("order_type"), settings)

            sale_code = buildCode(SaleOrder, "Sale", data.get("code"), request)
            sale_order = commonQuery.createRecord(
                SaleOrder,
                {
                    "customer_id": data.get("customer_id"),
                    "cashier_id": request.user.id,
                    "register_id": shift["register_id"] if shift else None,
                    "shift_id": shift["id"] if shift else None,
                    "code": sale_code,
                    "order_type": order_type,
                    "payment_status": "unpaid",
                    "discount_amount": data.get("discount_amount") or 0,
                    "discount_percentage": data.get("discount_percentage") or 0,
                    "coupon_discount_amount": data.get("coupon_discount_amount") or 0,
                    "shipping_amount": data.get("shipping_amount") or 0,
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
                + money(data.get("shipping_amount"))
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
            payment_summary = SalePaymentService.applyPayments(
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
            SaleValidationService.ensurePaymentRules(total, paid_amount, due_amount, customer, settings)

            payment_status = "paid" if due_amount == 0 else ("partially_paid" if paid_amount > 0 else "unpaid")

            if shift and change_amount > 0 and payment_summary["cash_paid_amount"] > 0:
                SaleRegisterService.recordChangeGiven(sale_order, shift, change_amount, request)

            sale_order = commonQuery.updateRecordById(
                SaleOrder,
                sale_order["id"],
                {
                    "subtotal": subtotal,
                    "total": total,
                    "tendered_amount": paid_amount,
                    "change_amount": change_amount,
                    "due_amount": due_amount,
                    "coupon_discount_amount": coupon_result["discount_amount"],
                    "total_items": total_items,
                    "total_quantity": total_quantity,
                    "payment_status": payment_status,
                    "final_payment_date": timezone.now() if due_amount == 0 else None,
                },
                request=request,
                tenant_config=True,
            )

            customer = SaleCustomerService.applyCustomerImpact(sale_order, request)
            reward = SaleRewardService.processRewards(sale_order, request) if settings.enable_customer_rewards else None

            if data.get("draft_id"):
                draft = commonQuery.findOneRecord(
                    CartDraft,
                    data["draft_id"],
                    request=request,
                    tenant_config=True,
                )
                if draft:
                    commonQuery.updateRecordById(
                        CartDraft,
                        draft["id"],
                        {"draft_status": "converted"},
                        request=request,
                        tenant_config=True,
                    )

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
                SalePayment,
                {"sale_order_id": sale_order_id},
                {"attributes": ["id", "amount"]},
                request=request,
                tenant_config=True,
            )
            paid_amount = sum([money(payment.get("amount")) for payment in payments], Decimal("0"))
            if paid_amount > 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Paid sale cannot be voided. Use refund flow instead.")

            returns = commonQuery.findAllRecords(
                ReturnOrder,
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
                SaleOrder,
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
            return successResponse("Sale voided successfully.", data=updated)

    @staticmethod
    def collectDue(sale_order_id, data, request):
        with transaction.atomic():
            sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
            if sale_order.get("payment_status") in ["void", "refunded"]:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Due cannot be collected for this sale.")

            remaining_due = money(sale_order.get("due_amount"))
            if remaining_due <= 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "This sale does not have any due amount.")
            if not data.get("payments"):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one payment is required.")

            settings = getBusinessSettings(request.user)
            shift = getCurrentShift(
                request,
                data.get("shift_id"),
                required=bool(settings.enable_cash_registers),
            )
            customer = SaleValidationService.ensureCustomer(sale_order.get("customer_id"), request)
            payment_summary = SalePaymentService.collectDuePayments(
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
                SaleOrder,
                sale_order_id,
                {
                    "due_amount": next_due,
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
                    CustomerCreditLedger,
                    {
                        "customer_id": customer["id"],
                        "amount": collected_amount,
                        "direction": "decrease",
                        "balance_after": next_owed_amount,
                        "reason": "sale_due_collection",
                        "reference_type": "sale_order",
                        "reference_id": sale_order_id,
                        "note": data.get("note") or f"Due collected for sale {sale_order['code']}",
                    },
                    request=request,
                    tenant_config=True,
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
            SaleOrder,
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
            SaleOrder,
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
        return successResponse("Installments retrieved successfully.", data=sale_data.get("installment_plan"))

    @staticmethod
    def createInstallments(sale_order_id, data, request):
        sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        lines = data.get("lines") or []
        if not lines:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one installment line is required.")
        if money(sale_order.get("due_amount")) <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Installments can be created only when due amount exists.")

        with transaction.atomic():
            plan = commonQuery.findOneRecord(
                InstallmentPlan,
                {"sale_order_id": sale_order_id},
                request=request,
                tenant_config=True,
            )
            if plan:
                InstallmentLine.objects.filter(
                    company_id=request.user.company_id,
                    branch_id=request.user.branch_id,
                    plan_id=plan["id"],
                ).delete()
                plan = commonQuery.updateRecordById(
                    InstallmentPlan,
                    plan["id"],
                    {
                        "total_installments": data.get("total_installments") or len(lines),
                        "total_amount": data.get("total_amount") or sale_order.get("due_amount") or 0,
                        "minimum_first_payment": data.get("minimum_first_payment") or 0,
                        "final_payment_date": data.get("final_payment_date") or None,
                    },
                    request=request,
                    tenant_config=True,
                )
            else:
                plan = commonQuery.createRecord(
                    InstallmentPlan,
                    {
                        "sale_order_id": sale_order_id,
                        "total_installments": data.get("total_installments") or len(lines),
                        "total_amount": data.get("total_amount") or sale_order.get("due_amount") or 0,
                        "minimum_first_payment": data.get("minimum_first_payment") or 0,
                        "final_payment_date": data.get("final_payment_date") or None,
                    },
                    request=request,
                    tenant_config=True,
                )

            for line in lines:
                commonQuery.createRecord(
                    InstallmentLine,
                    {
                        "plan_id": plan["id"],
                        "due_date": line.get("due_date"),
                        "amount": line.get("amount") or 0,
                        "paid_amount": 0,
                        "installment_status": "pending",
                    },
                    request=request,
                    tenant_config=True,
                )

            commonQuery.updateRecordById(
                SaleOrder,
                sale_order_id,
                {"support_installments": True},
                request=request,
                tenant_config=True,
            )
            sale_data = SaleService.buildSaleDetail(sale_order_id, request)
            return successResponse("Installments saved successfully.", data=sale_data.get("installment_plan"))

    @staticmethod
    def updateInstallment(sale_order_id, installment_id, data, request):
        SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        plan = commonQuery.findOneRecord(
            InstallmentPlan,
            {"sale_order_id": sale_order_id},
            request=request,
            tenant_config=True,
        )
        if plan is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Installment plan not found.")
        installment = commonQuery.findOneRecord(
            InstallmentLine,
            {"id": installment_id, "plan_id": plan["id"]},
            request=request,
            tenant_config=True,
        )
        if installment is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Installment not found.")
        updated = commonQuery.updateRecordById(
            InstallmentLine,
            installment_id,
            data,
            request=request,
            tenant_config=True,
        )
        return successResponse("Installment updated successfully.", data=updated)

    @staticmethod
    def deleteInstallment(sale_order_id, installment_id, request):
        SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        plan = commonQuery.findOneRecord(
            InstallmentPlan,
            {"sale_order_id": sale_order_id},
            request=request,
            tenant_config=True,
        )
        if plan is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Installment plan not found.")
        installment = commonQuery.findOneRecord(
            InstallmentLine,
            {"id": installment_id, "plan_id": plan["id"]},
            request=request,
            tenant_config=True,
        )
        if installment is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Installment not found.")
        if money(installment.get("paid_amount")) > 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Paid installment cannot be deleted.")
        InstallmentLine.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            id=installment_id,
            plan_id=plan["id"],
        ).delete()
        return successResponse("Installment deleted successfully.")

    @staticmethod
    def payInstallment(sale_order_id, installment_id, data, request):
        sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        plan = commonQuery.findOneRecord(
            InstallmentPlan,
            {"sale_order_id": sale_order_id},
            request=request,
            tenant_config=True,
        )
        if plan is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Installment plan not found.")
        installment = commonQuery.findOneRecord(
            InstallmentLine,
            {"id": installment_id, "plan_id": plan["id"]},
            request=request,
            tenant_config=True,
        )
        if installment is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Installment not found.")

        amount = money(data.get("amount"))
        if amount <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Installment amount must be greater than 0.")
        remaining = money(installment.get("amount")) - money(installment.get("paid_amount"))
        if amount > remaining:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Installment payment exceeds remaining amount.")

        with transaction.atomic():
            settings = getBusinessSettings(request.user)
            shift = getCurrentShift(
                request,
                data.get("shift_id"),
                required=bool(settings.enable_cash_registers),
            )
            customer = SaleValidationService.ensureCustomer(sale_order.get("customer_id"), request)
            SalePaymentService.collectDuePayments(
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

            updated_paid = money(installment.get("paid_amount")) + amount
            commonQuery.updateRecordById(
                InstallmentLine,
                installment_id,
                {
                    "paid_amount": updated_paid,
                    "installment_status": "paid" if updated_paid >= money(installment.get("amount")) else "partial",
                },
                request=request,
                tenant_config=True,
            )

            next_due = max(money(sale_order.get("due_amount")) - amount, Decimal("0"))
            next_tendered = money(sale_order.get("tendered_amount")) + amount
            commonQuery.updateRecordById(
                SaleOrder,
                sale_order_id,
                {
                    "due_amount": next_due,
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
                    CustomerCreditLedger,
                    {
                        "customer_id": customer["id"],
                        "amount": amount,
                        "direction": "decrease",
                        "balance_after": next_owed_amount,
                        "reason": "sale_installment_payment",
                        "reference_type": "sale_order",
                        "reference_id": sale_order_id,
                        "note": data.get("note") or f"Installment payment for sale {sale_order['code']}",
                    },
                    request=request,
                    tenant_config=True,
                )

            refreshed_sale = SaleService.buildSaleDetail(sale_order_id, request)
            return successResponse("Installment paid successfully.", data=refreshed_sale)

    @staticmethod
    def createReturn(sale_order_id, data, request):
        SaleReturnValidationService.ensureReturnType(data.get("return_type") or "refund")

        with transaction.atomic():
            sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
            settings = getBusinessSettings(request.user)
            customer = SaleValidationService.ensureCustomer(sale_order.get("customer_id"), request) if sale_order.get("customer_id") else None
            prepared = SaleReturnValidationService.validateItems(sale_order, data.get("items") or [], request)

            return_order = commonQuery.createRecord(
                ReturnOrder,
                {
                    "sale_order_id": sale_order["id"],
                    "customer_id": sale_order.get("customer_id"),
                    "cashier_id": request.user.id,
                    "return_type": data.get("return_type") or "refund",
                    "return_status": "processed",
                    "subtotal": prepared["subtotal"],
                    "tax_amount": prepared["tax_amount"],
                    "total": prepared["total"],
                    "note": data.get("note") or "",
                },
                request=request,
                tenant_config=True,
            )

            created_items = []
            for item in prepared["items"]:
                return_item = commonQuery.createRecord(
                    ReturnItem,
                    {
                        "return_order_id": return_order["id"],
                        "sale_item_id": item["sale_item"]["id"],
                        "quantity": item["quantity"],
                        "unit_price": item["unit_price"],
                        "total": item["line_total"] + item["tax_amount"],
                        "condition": item["condition"],
                    },
                    request=request,
                    tenant_config=True,
                )
                created_items.append(return_item)

                refunded_qty = SaleReturnValidationService.refundedQuantity(item["sale_item"]["id"], request)
                item_status = "returned" if refunded_qty >= quantity(item["sale_item"].get("quantity")) else "partially_returned"
                commonQuery.updateRecordById(
                    SaleItem,
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
            updated_sale = SaleRefundService.updateSalePaymentStatus(sale_order["id"], request)

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
            ReturnOrder,
            {"sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "customer_id",
                    "customer__name",
                    "cashier_id",
                    "cashier__full_name",
                    "return_type",
                    "return_status",
                    "subtotal",
                    "tax_amount",
                    "total",
                    "note",
                    "created_at",
                ],
                "order": ["-id"],
            },
            request=request,
            tenant_config=True,
        )
        for refund in refunds:
            refund["items"] = commonQuery.findAllRecords(
                ReturnItem,
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
                },
                request=request,
                tenant_config=True,
            )
            refund["payments"] = commonQuery.findAllRecords(
                RefundPayment,
                {"return_order_id": refund["id"]},
                {
                    "attributes": [
                        "id",
                        "payment_type",
                        "amount",
                        "refunded_at",
                        "reference_number",
                        "note",
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
            ReturnItem,
            {"return_order__sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "return_order_id",
                    "return_order__return_type",
                    "sale_item_id",
                    "sale_item__product__name",
                    "quantity",
                    "unit_price",
                    "total",
                    "condition",
                    "created_at",
                ],
                "order": ["-id"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Refunded sale items retrieved successfully.", data=refunded_items)
