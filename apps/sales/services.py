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
from apps.customers.models import Customer, CustomerCreditLedger
from apps.inventory.models import StockLedger
from apps.payments.models import SalePayment, normalizePaymentType, paymentTypeValues
from apps.registers.models import CashierShift, CashRegisterEntry
from apps.rewards.services import CustomerRewardService
from apps.sales.models import SaleItem, SaleOrder


def money(value):
    return Decimal(str(value or 0))


def quantity(value):
    return Decimal(str(value or 0))


def getCurrentShift(request, shift_id=None):
    where = {"id": shift_id} if shift_id else {"cashier_id": request.user.id, "shift_status": "open"}
    shift = commonQuery.findOneRecord(
        CashierShift,
        where,
        request=request,
        tenant_config=True,
    )
    if shift is None or shift.get("shift_status") != "open":
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


class SalePaymentService:
    @staticmethod
    def applyPayments(sale_order, payments, shift, request):
        paid_amount = Decimal("0")

        for payment in payments or []:
            amount = money(payment.get("amount"))
            if amount <= 0:
                continue

            payment_type = normalizePaymentType(payment.get("payment_type"))
            if payment_type not in paymentTypeValues():
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid payment type.")

            sale_payment = commonQuery.createRecord(
                SalePayment,
                {
                    "sale_order_id": sale_order["id"],
                    "payment_type": payment_type,
                    "shift_id": shift["id"],
                    "amount": amount,
                    "paid_at": timezone.now(),
                    "reference_number": payment.get("reference_number") or "",
                    "note": payment.get("note") or "",
                },
                request=request,
                tenant_config=True,
            )
            paid_amount += amount

            if payment_type == "cash-payment":
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
                        "payment_type": payment_type,
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

        CashierShift.objects.filter(id=shift["id"]).update(total_sales_amount=F("total_sales_amount") + sale_order["total"])
        return paid_amount


class SaleCustomerService:
    @staticmethod
    def applyCustomerImpact(sale_order, request):
        customer_id = sale_order.get("customer_id")
        if not customer_id:
            return None

        Customer.objects.filter(id=customer_id).update(
            total_sales=F("total_sales") + sale_order["total"],
            total_sales_count=F("total_sales_count") + 1,
            owed_amount=F("owed_amount") + sale_order["due_amount"],
        )

        if money(sale_order.get("due_amount")) > 0:
            customer = commonQuery.findOneRecord(
                Customer,
                customer_id,
                request=request,
                tenant_config=True,
            )
            commonQuery.createRecord(
                CustomerCreditLedger,
                {
                    "customer_id": customer_id,
                    "amount": sale_order["due_amount"],
                    "direction": "increase",
                    "balance_after": customer.get("owed_amount") if customer else sale_order["due_amount"],
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
            shift = getCurrentShift(request, data.get("shift_id"))

            if data.get("customer_id"):
                customer = commonQuery.findOneRecord(
                    Customer,
                    data["customer_id"],
                    request=request,
                    tenant_config=True,
                )
                if customer is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")

            sale_code = buildCode(SaleOrder, "Sale", data.get("code"), request)
            sale_order = commonQuery.createRecord(
                SaleOrder,
                {
                    "customer_id": data.get("customer_id"),
                    "cashier_id": request.user.id,
                    "register_id": shift["register_id"],
                    "shift_id": shift["id"],
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
                - money(data.get("coupon_discount_amount"))
                + money(data.get("shipping_amount"))
            )
            paid_amount = SalePaymentService.applyPayments(sale_order, data.get("payments") or [], shift, request)
            due_amount = max(total - paid_amount, Decimal("0"))
            change_amount = max(paid_amount - total, Decimal("0"))
            payment_status = "paid" if due_amount == 0 else ("partially_paid" if paid_amount > 0 else "unpaid")

            sale_order = commonQuery.updateRecordById(
                SaleOrder,
                sale_order["id"],
                {
                    "subtotal": subtotal,
                    "total": total,
                    "tendered_amount": paid_amount,
                    "change_amount": change_amount,
                    "due_amount": due_amount,
                    "total_items": total_items,
                    "total_quantity": total_quantity,
                    "payment_status": payment_status,
                },
                request=request,
                tenant_config=True,
            )

            customer = SaleCustomerService.applyCustomerImpact(sale_order, request)
            reward = SaleRewardService.processRewards(sale_order, request)

            return successResponse(
                "Sale created successfully.",
                data={
                    **sale_order,
                    "items": sale_items,
                    "customer": customer,
                    "reward": reward,
                    "paid_amount": paid_amount,
                },
            )
