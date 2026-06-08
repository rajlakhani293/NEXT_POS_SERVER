# type: ignore
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import Product
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode
from apps.common.responses import successResponse
from apps.customers.models import Customer, CustomerAccountHistory, CustomerCreditLedger, CustomerWalletTransaction
from apps.inventory.models import StockLedger
from apps.payments.models import SalePayment
from apps.payments.services import PaymentTypeService
from apps.promotions.models import AppliedCoupon, Coupon, CouponCategory, CouponCustomer, CouponCustomerGroup, CouponProduct, CustomerCoupon
from apps.registers.models import CashierShift, CashRegisterEntry
from apps.rewards.services import CustomerRewardService
from apps.sales.models import SaleItem, SaleOrder
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
        unit_price = money(item.get("unit_price") if item.get("unit_price") is not None else product.get("selling_price"))
        discount_amount = money(item.get("discount_amount"))
        tax_amount = money(item.get("tax_amount"))
        line_total = (item_qty * unit_price) - discount_amount + tax_amount

        sale_item = commonQuery.createRecord(
            SaleItem,
            {
                "sale_order_id": sale_order["id"],
                "product_id": product["id"],
                "unit_id": item.get("unit_id") or product.get("unit_id"),
                "quantity": item_qty,
                "unit_price": unit_price,
                "discount_amount": discount_amount,
                "tax_amount": tax_amount,
                "total": line_total,
                "cost_price": product.get("purchase_price") or 0,
            },
            request=request,
            tenant_config=True,
        )

        if product.get("track_stock") and product.get("product_type") == "stock":
            available_stock = quantity(product.get("current_stock"))
            if available_stock < item_qty:
                raise api_error(400, ErrorCodes.BAD_REQUEST, f"Insufficient stock for {product.get('name')}.")
            new_balance = available_stock - item_qty
            Product.objects.filter(id=product["id"]).update(current_stock=F("current_stock") - item_qty)
            commonQuery.createRecord(
                StockLedger,
                {
                    "product_id": product["id"],
                    "entry_type": "sale",
                    "quantity": item_qty * Decimal("-1"),
                    "unit_cost": product.get("purchase_price") or 0,
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


class SaleService:
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

            sale_code = buildCode(SaleOrder, "Sale", data.get("code"), request)
            sale_order = commonQuery.createRecord(
                SaleOrder,
                {
                    "customer_id": data.get("customer_id"),
                    "cashier_id": request.user.id,
                    "register_id": shift["register_id"] if shift else None,
                    "shift_id": shift["id"] if shift else None,
                    "code": sale_code,
                    "order_type": data.get("order_type") or "pos",
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

            if due_amount > 0 and not settings.allow_partial_orders:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Partial or unpaid sales are not allowed.")
            if due_amount > 0 and not customer:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer is required when sale has due amount.")
            if due_amount > 0 and not settings.enable_credit_account:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer credit account is disabled.")

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
