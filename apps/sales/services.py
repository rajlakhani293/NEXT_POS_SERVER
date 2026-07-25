# type: ignore
import json
from datetime import datetime, time
from types import SimpleNamespace
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.accounting.services import AccountingService
from apps.catalog.models import Product, ProductHistory, ProductUnitQuantity, Tax
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
from apps.common.tenantDefaults import DEFAULT_ORDER_SETTINGS
from apps.customers.models import (
    Customer,
    CustomerAccountHistory,
    CustomerCoupon,
    CustomerGroup,
    CustomerReward,
)
from apps.customers.services import CustomerAccountService
from apps.settings.models import PaymentType
from apps.settings.models import Notification, Option
from apps.settings.services import OptionSettingService, PaymentTypeService
from apps.promotions.models import OrdersCoupon, Coupon, CouponCategory, CouponCustomerGroup, CouponProduct
from apps.registers.models import Register, RegistersHistory
from apps.registers.services import RegisterService
from apps.reports.services import ReportService
from apps.rewards.services import CustomerRewardService
from apps.sales.models import (
    OrderCount,
    OrderInstalment,
    OrderStorage,
    OrderPayment,
    OrderSetting,
    OrderTax,
    OrderAddress,
    OrdersProductsRefund,
    OrdersRefund,
    OrdersProduct,
    Order,
)
from apps.accounts.models import User


def getOptionSettings(user):
    option = OptionSettingService.ensureSettings(user)
    return SimpleNamespace(**OptionSettingService.optionValue(option))


def saleDueAmount(sale_order):
    return max(money((sale_order or {}).get("total")) - money((sale_order or {}).get("tendered_amount")), Decimal("0"))


def normalizeOrderPayments(payments):
    for payment in payments or []:
        payment["payment_type"] = payment.get("identifier")
        payment["amount"] = payment.get("value")
    return payments


def parseInstallmentDate(value):
    if not value:
        return value
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value
    parsed_datetime = parse_datetime(str(value))
    if parsed_datetime:
        if timezone.is_naive(parsed_datetime):
            return timezone.make_aware(parsed_datetime, timezone.get_current_timezone())
        return parsed_datetime
    parsed_date = parse_date(str(value))
    if parsed_date:
        return timezone.make_aware(datetime.combine(parsed_date, time.min), timezone.get_current_timezone())
    return value


def parseListDate(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    parsed_date = parse_date(str(value))
    if parsed_date:
        return parsed_date
    parsed_datetime = parse_datetime(str(value))
    if parsed_datetime:
        return parsed_datetime.date()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except Exception:
        return None


def yesNo(value):
    if isinstance(value, str):
        return "yes" if value.lower() in {"yes", "true", "1", "enabled"} else "no"
    return "yes" if bool(value) else "no"


def generateOrderCode(request, created_at=None):
    if not transaction.get_connection().in_atomic_block:
        with transaction.atomic():
            return generateOrderCode(request, created_at)

    from apps.settings.services import OptionSettingService
    code_type = OptionSettingService.getOptionValue(request.user.company, request.user.branch, "orders_code_type", "date_sequential")
    if code_type == "sequential":
        code_type = "date_sequential"

    if code_type in ["random", "random_code"]:
        import uuid
        while True:
            code = uuid.uuid4().hex[:8].upper()
            exists = commonQuery.branchScopedQueryset(Order, {"code": code}, request).exists()
            if not exists:
                return code

    now = timezone.localtime(created_at or timezone.now())
    today = now.date()
    day_start = timezone.make_aware(
        datetime.combine(today, time.min),
        timezone.get_current_timezone(),
    )

    counter = (
        commonQuery.branchScopedQueryset(OrderCount, {"date": day_start}, request)
        .select_for_update()
        .first()
    )
    if counter is None:
        counter = commonQuery.createInstance(
            OrderCount,
            {"date": day_start, "count": 1},
            request=request,
            tenant_config=True,
        )

    count = counter.count
    counter.count = counter.count + 1
    counter.save(update_fields=["count"])

    while True:
        code = f"{now:%y%m%d}-{count:03d}"
        exists = commonQuery.branchScopedQueryset(Order, {"code": code}, request).exists()
        if not exists:
            return code
        count += 1
        counter.count = max(counter.count, count + 1)
        counter.save(update_fields=["count"])


def getCurrentRegisterContext(request, register_id=None, required=True):
    filters = {"status": 0}
    if register_id:
        filters["id"] = register_id
    else:
        filters["used_by_id"] = request.user.id

    register = (
        commonQuery.branchScopedQueryset(Register, filters, request)
        .filter(register_status__in=[Register.STATUS_OPENED, Register.STATUS_INUSE])
        .values("id", "name", "register_status", "balance")
        .first()
    )
    if register is None and required:
        raise api_error(400, ErrorCodes.BAD_REQUEST, "Open cash register is required.")
    if register is None:
        return None
    return {
        "register_id": register["id"],
        "name": register["name"],
        "register_status": register["register_status"],
        "balance": register["balance"],
    }


def parseDraftSnapshot(note):
    if not note:
        return {}
    try:
        data = json.loads(note)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"note": note}


class SaleTaxService:
    @staticmethod
    def normalizeTaxType(tax_type):
        return tax_type if tax_type in ["inclusive", "exclusive"] else None

    @staticmethod
    def priceWithoutTax(tax_type, rate, value):
        value = money(value)
        rate = money(rate)
        if tax_type == "inclusive" and rate > 0:
            return (value / (Decimal("100") + rate)) * Decimal("100")
        return value

    @staticmethod
    def priceWithTax(tax_type, rate, value):
        value = money(value)
        rate = money(rate)
        if tax_type == "exclusive" and rate > 0:
            return value + ((value * rate) / Decimal("100"))
        return value

    @staticmethod
    def taxValue(tax_type, rate, value):
        tax_type = SaleTaxService.normalizeTaxType(tax_type)
        if tax_type == "inclusive":
            return money(value) - SaleTaxService.priceWithoutTax(tax_type, rate, value)
        if tax_type == "exclusive":
            return SaleTaxService.priceWithTax(tax_type, rate, value) - money(value)
        return Decimal("0")

    @staticmethod
    def taxRowsForGroup(tax_group_id, request):
        if not tax_group_id:
            return []
        return commonQuery.findAllRecords(
            Tax,
            {"tax_group_id": tax_group_id, "status__in": [0, 1]},
            {"attributes": ["id", "name", "rate"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def summarizeRate(taxes):
        return sum((money(tax.get("rate")) for tax in taxes), Decimal("0"))

    @staticmethod
    def splitTaxValue(total_tax, taxes):
        rate = SaleTaxService.summarizeRate(taxes)
        if rate <= 0:
            return []
        return [
            {
                "tax_id": tax.get("id"),
                "tax_name": tax.get("name"),
                "rate": money(tax.get("rate")),
                "tax_value": (money(total_tax) * money(tax.get("rate"))) / rate,
            }
            for tax in taxes
        ]

    @staticmethod
    def computeProductTax(item, product, line_base, settings, request):
        if getattr(settings, "pos_vat", "disabled") != "products_vat":
            return {"tax_amount": Decimal("0"), "tax_type": None, "tax_group_id": None, "price_net": line_base, "price_gross": line_base}

        tax_group_id = item.get("tax_group_id") or product.get("tax_group_id")
        tax_type = SaleTaxService.normalizeTaxType(item.get("tax_type") or product.get("tax_type"))
        taxes = SaleTaxService.taxRowsForGroup(tax_group_id, request)
        rate = SaleTaxService.summarizeRate(taxes)
        tax_amount = SaleTaxService.taxValue(tax_type, rate, line_base)
        return {
            "tax_amount": tax_amount,
            "tax_type": tax_type,
            "tax_group_id": tax_group_id if taxes else None,
            "price_net": SaleTaxService.priceWithoutTax(tax_type, rate, line_base),
            "price_gross": SaleTaxService.priceWithTax(tax_type, rate, line_base),
        }

    @staticmethod
    def resolveOrderTaxConfig(data, settings, request):
        if getattr(settings, "pos_vat", "disabled") not in ["flat_vat", "variable_vat"]:
            return {"tax_group_id": None, "tax_type": None, "taxes": []}

        tax_group_id = data.get("tax_group_id") or getattr(settings, "pos_tax_group", None)
        tax_type = SaleTaxService.normalizeTaxType(data.get("tax_type") or getattr(settings, "pos_tax_type", None))
        taxes = SaleTaxService.taxRowsForGroup(tax_group_id, request)
        if not taxes or not tax_type:
            return {"tax_group_id": None, "tax_type": None, "taxes": []}
        return {"tax_group_id": tax_group_id, "tax_type": tax_type, "taxes": taxes}

    @staticmethod
    def createOrderTaxes(sale_order_id, tax_type, taxes, taxable_amount, request):
        total_tax = SaleTaxService.taxValue(tax_type, SaleTaxService.summarizeRate(taxes), taxable_amount)
        commonQuery.branchScopedQueryset(OrderTax, {"sale_order_id": sale_order_id}, request).delete()
        created = []
        for row in SaleTaxService.splitTaxValue(total_tax, taxes):
            created.append(
                commonQuery.createRecord(
                    OrderTax,
                    {
                        "sale_order_id": sale_order_id,
                        "tax_id": row["tax_id"],
                        "tax_name": row["tax_name"],
                        "rate": row["rate"],
                        "tax_value": row["tax_value"],
                    },
                    request=request,
                    tenant_config=True,
                )
            )
        return {"total_tax": total_tax, "taxes": created}


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
    def resolveBarcodeItem(item, request):
        barcode = item.get("barcode")
        product_id = item.get("product_id")
        
        if barcode:
            from apps.catalog.services import ProductService
            from apps.common.commonQuery import safeAuthContext
            from apps.catalog.models import ProductUnitQuantity, Product
            
            ctx = safeAuthContext(request)
            company = ctx.get("company_id")
            branch = ctx.get("branch_id")
            
            if ProductService.isScaleBarcode(barcode, company, branch):
                parsed = ProductService.parseScaleBarcode(barcode, company, branch)
                scale_plu = parsed["product_code"]
                scale_qty = parsed["value"]
                
                # Overwrite quantity from scale barcode
                item["quantity"] = scale_qty
                
                unit_quantity = commonQuery.findOneRecord(
                    ProductUnitQuantity,
                    {"scale_plu": scale_plu},
                    request=request,
                    tenant_config=True,
                )
                if unit_quantity is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, f"Product with scale PLU '{scale_plu}' not found.")
                
                product_id = unit_quantity["product_id"]
                item["product_id"] = product_id
                item["unit_quantity_id"] = unit_quantity["id"]
                item["unit_id"] = unit_quantity["unit_id"]
            else:
                unit_quantity = commonQuery.findOneRecord(
                    ProductUnitQuantity,
                    {"barcode": barcode},
                    request=request,
                    tenant_config=True,
                )
                if unit_quantity:
                    product_id = unit_quantity["product_id"]
                    item["product_id"] = product_id
                    item["unit_quantity_id"] = unit_quantity["id"]
                    item["unit_id"] = unit_quantity["unit_id"]
                else:
                    product_rec = commonQuery.findOneRecord(
                        Product,
                        {"barcode": barcode},
                        request=request,
                        tenant_config=True,
                    )
                    if product_rec:
                        product_id = product_rec["id"]
                        item["product_id"] = product_id
                    else:
                        raise api_error(404, ErrorCodes.NOT_FOUND, f"Product with barcode '{barcode}' not found.")
                        
        if not product_id:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Product ID or Barcode is required.")
        
        return product_id

    @staticmethod
    def applySaleItem(item, sale_order, settings, request):
        product_id = SaleStockService.resolveBarcodeItem(item, request)
        product = commonQuery.findOneRecord(
            Product,
            product_id,
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
        line_base = (item_qty * unit_price) - discount_amount
        tax_result = SaleTaxService.computeProductTax(item, product, line_base, settings, request)
        tax_amount = tax_result["tax_amount"]
        line_total = (
            line_base + tax_amount
            if tax_result["tax_type"] == "exclusive" and getattr(settings, "pos_preferred_price", "net_prices") == "net_prices"
            else line_base
        )
        unit_name = item.get("unit_name")
        if not unit_name and unit_quantity:
            unit_name = unit_quantity.get("unit__name") or unit_quantity.get("unit_name")

        sale_item = commonQuery.createRecord(
            OrdersProduct,
            {
                "sale_order_id": sale_order["id"],
                "product_id": product["id"],
                "name": item.get("name") or product.get("name") or "Unnamed Product",
                "unit_name": unit_name,
                "mode": item.get("mode") or "normal",
                "product_type": item.get("product_type") or product.get("product_type") or "product",
                "rate": money(item.get("rate")),
                "unit_id": unit_id,
                "unit_quantity_id": unit_quantity.get("id") if unit_quantity else None,
                "quantity": item_qty,
                "unit_price": unit_price,
                "discount_amount": discount_amount,
                "tax_amount": tax_amount,
                "tax_type": tax_result["tax_type"],
                "tax_group_id": tax_result["tax_group_id"],
                "price_net": tax_result["price_net"] / item_qty if item_qty else Decimal("0"),
                "price_gross": tax_result["price_gross"] / item_qty if item_qty else Decimal("0"),
                "total_price_net": tax_result["price_net"],
                "total_price_gross": tax_result["price_gross"],
                "total": line_total,
                "cost_price": default_purchase_price or 0,
            },
            request=request,
            tenant_config=True,
        )

        return sale_item, line_total, item_qty

    @staticmethod
    def recordSaleStock(sale_order, request):
        if sale_order.get("payment_status") not in ["paid", "partially_paid"]:
            return []

        items = commonQuery.findAllRecords(
            OrdersProduct,
            {"sale_order_id": sale_order["id"]},
            {
                "attributes": [
                    "id",
                    "product_id",
                    "unit_id",
                    "unit_quantity_id",
                    "quantity",
                    "unit_price",
                    "total",
                ]
            },
            request=request,
            tenant_config=True,
        )
        histories = []
        for item in items:
            already_recorded = commonQuery.findOneRecord(
                ProductHistory,
                {
                    "order_id": sale_order["id"],
                    "order_product_id": item["id"],
                    "operation_type": ProductHistory.ACTION_SOLD,
                },
                request=request,
                tenant_config=True,
            )
            if already_recorded:
                continue

            product = commonQuery.findOneRecord(
                Product,
                item["product_id"],
                request=request,
                tenant_config=True,
            )
            if not product or not SaleStockService.stockEnabled(product):
                continue

            unit_quantity = SaleStockService.resolveUnitQuantity(
                product,
                {"unit_quantity_id": item.get("unit_quantity_id"), "unit_id": item.get("unit_id")},
                request,
                required=True,
            )
            histories.append(
                ProductStockService.recordStockHistory(
                    ProductHistory.ACTION_SOLD,
                    {
                        "product_id": product["id"],
                        "order_id": sale_order["id"],
                        "order_product_id": item["id"],
                        "unit_id": unit_quantity.get("unit_id"),
                        "quantity": item.get("quantity"),
                        "unit_price": item.get("unit_price") or 0,
                        "total_price": item.get("total") or 0,
                        "description": f"Sale {sale_order['code']}",
                    },
                    request,
                )
            )
        return histories


class SaleValidationService:
    PROCESS_STATUSES = ["pending", "ongoing", "ready", "not-available"]
    DELIVERY_STATUSES = ["pending", "ongoing", "delivered", "error", "not-available"]

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
    def statusDefaultsForOrderType(order_type):
        if SaleValidationService.normalizeOrderType(order_type) == "delivery":
            return {"process_status": "pending", "delivery_status": "pending"}
        return {"process_status": "not-available", "delivery_status": "not-available"}

    @staticmethod
    def ensureProcessingStatusAllowed(status, sale_order):
        if sale_order.get("order_type") != "delivery":
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Processing status is only available for delivery orders.")
        if status not in SaleValidationService.PROCESS_STATUSES or status == "not-available":
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid processing status.")
        return status

    @staticmethod
    def ensureDeliveryStatusAllowed(status, sale_order):
        if sale_order.get("order_type") != "delivery":
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Delivery status is only available for delivery orders.")
        if status not in SaleValidationService.DELIVERY_STATUSES or status == "not-available":
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid delivery status.")
        return status

    @staticmethod
    def orderSettingValue(key, sale_order, option_rows):
        order_values = {
            "order_type": sale_order.get("order_type") or sale_order.get("type") or "takeaway",
            "discount_type": sale_order.get("discount_type") or "",
            "discount_value": str(sale_order.get("discount_percentage") or sale_order.get("discount_amount") or 0),
            "tax_type": sale_order.get("tax_type") or "",
            "tax_group": str(sale_order.get("tax_group_id") or ""),
            "note_visibility": sale_order.get("note_visibility") or "hidden",
        }
        if key in order_values:
            return order_values[key]
        return option_rows.get(key)

    @staticmethod
    def ensurePaymentRules(total, paid_amount, due_amount, customer, settings, request):
        if paid_amount > total:
            return
        if due_amount <= 0:
            return
        if paid_amount > 0 and not getattr(settings, "orders_allow_partial", getattr(settings, "allow_partial_orders", False)):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Partially paid sales are not allowed.")
        if paid_amount <= 0 and not settings.orders_allow_unpaid:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unpaid sales are not allowed.")
        if not customer:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer is required when sale has due amount.")
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
            if (
                minimum_payment > 0
                and paid_amount < minimum_payment
                and not settings.orders_allow_unpaid
            ):
                raise api_error(
                    400,
                    ErrorCodes.BAD_REQUEST,
                    f"A minimum payment of {minimum_payment:.2f} is required for this customer group.",
                )

    @staticmethod
    def ensurePartialOrdersAllowedForInstalments(data, settings):
        has_instalments = bool(data.get("instalments"))
        supports_instalments = data.get("support_instalments") is True
        if (has_instalments or supports_instalments) and not getattr(settings, "orders_allow_partial", False):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Partially paid orders are disabled.")

    @staticmethod
    def ensurePartialDuePaymentAllowed(collected_amount, remaining_due, settings):
        if collected_amount <= 0 or collected_amount >= remaining_due:
            return
        if not getattr(settings, "orders_allow_partial", False):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Partially paid orders are disabled.")

    @staticmethod
    def ensureStrictInstallmentPaymentAllowed(sale_order, settings, request):
        if not getattr(settings, "orders_strict_instalments", False):
            return
        if not sale_order.get("support_instalments"):
            return
        has_installments = commonQuery.branchScopedQueryset(
            OrderInstalment,
            {"sale_order_id": sale_order.get("id")},
            request,
        ).exists()
        if not has_installments:
            return
        today = timezone.localdate()
        payment_due_today = commonQuery.branchScopedQueryset(
            OrderInstalment,
            {
                "sale_order_id": sale_order.get("id"),
                "paid": False,
                "date__date": today,
            },
            request,
        ).exists()
        if not payment_due_today:
            raise api_error(
                404,
                ErrorCodes.NOT_FOUND,
                "No payment is expected at the moment. If the customer want to pay early, consider adjusting instalment payments date.",
            )


class SaleRegisterService:
    @staticmethod
    def recordCashOrderPayment(sale_order, order_payment, register_context, amount, request):
        payment_type = commonQuery.branchScopedQueryset(
            PaymentType,
            {"identifier": order_payment.get("identifier"), "status__in": [0, 1]},
            request,
        ).values("id").first()
        return RegisterService.recordHistory(
            register_context["register_id"],
            RegistersHistory.ACTION_ORDER_PAYMENT,
            amount,
            request,
            f"Cash payment for order {sale_order.get('code')}",
            payment_id=order_payment.get("id"),
            payment_type_id=payment_type["id"] if payment_type else 0,
            order_id=sale_order.get("id"),
        )

    @staticmethod
    def recordChangeGiven(sale_order, register_context, change_amount, request):
        return RegisterService.recordHistory(
            register_context["register_id"],
            RegistersHistory.ACTION_ORDER_CHANGE,
            change_amount,
            request,
            f"Change given for order {sale_order.get('code')}",
            payment_type_id=RegisterService.defaultChangePaymentTypeId(request),
            order_id=sale_order.get("id"),
        )


class SaleCustomerAccountService:
    @staticmethod
    def applyAccountPayment(customer, sale_order, amount, payment_note, request):
        CustomerAccountService.saveTransaction(
            customer["id"],
            "payment",
            amount,
            request=request,
            description=payment_note or f"Sale payment for {sale_order['code']}",
            order_id=sale_order["id"],
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
                    "minimum_cart_value": coupon.get("minimum_cart_value") or 0,
                    "maximum_cart_value": coupon.get("maximum_cart_value") or 0,
                    "limit_usage": coupon.get("limit_usage") or 0,
                    "discount_amount": discount_amount,
                    "counted": False,
                },
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
    def existingPayments(sale_order_id, request):
        return commonQuery.findAllRecords(
            OrderPayment,
            {"sale_order_id": sale_order_id},
            {"attributes": ["id", "identifier", "value"]},
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def validatePreservedPayments(sale_order, payments, request):
        existing_payments = OrderPaymentService.existingPayments(sale_order["id"], request)
        existing_by_id = {payment["id"]: payment for payment in existing_payments}
        payload_by_id = {
            int(payment["id"]): payment
            for payment in payments or []
            if payment.get("id")
        }

        missing_ids = set(existing_by_id.keys()) - set(payload_by_id.keys())
        if missing_ids:
            raise api_error(
                400,
                ErrorCodes.BAD_REQUEST,
                "Existing sale payments must be preserved while updating a partially paid sale.",
            )

        for payment_id, payment in payload_by_id.items():
            existing = existing_by_id.get(payment_id)
            if existing is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Sale payment not found.")
            requested_type = payment.get("payment_type")
            if requested_type and requested_type != existing.get("identifier"):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Existing sale payment type cannot be changed.")
            if money(payment.get("amount")) != money(existing.get("value")):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Existing sale payment amount cannot be changed.")

        paid_amount = sum((money(payment.get("value")) for payment in existing_payments), Decimal("0"))
        cash_paid_amount = sum(
            (
                money(payment.get("value"))
                for payment in existing_payments
                if payment.get("identifier") == "cash-payment"
            ),
            Decimal("0"),
        )
        return {
            "paid_amount": paid_amount,
            "cash_paid_amount": cash_paid_amount,
            "existing_payment_ids": set(existing_by_id.keys()),
        }

    @staticmethod
    def splitNewPayments(payments):
        return [payment for payment in payments or [] if not payment.get("id")]

    @staticmethod
    def applyPayments(sale_order, payments, shift, customer, settings, request):
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

            if shift:
                SaleRegisterService.recordCashOrderPayment(sale_order, order_payment, shift, amount, request)
            if payment_type == "cash-payment":
                cash_paid_amount += amount
            elif payment_type == "account-payment":
                SaleCustomerAccountService.applyAccountPayment(customer, sale_order, amount, payment.get("note"), request)

        return {
            "paid_amount": paid_amount,
            "cash_paid_amount": cash_paid_amount,
            "payment_ids": payment_ids,
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

            if shift:
                SaleRegisterService.recordCashOrderPayment(sale_order, order_payment, shift, amount, request)
            if payment_type == "cash-payment":
                cash_paid_amount += amount
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
        update_fields = {"owed_amount": F("owed_amount") + due_amount}
        if sale_order.get("payment_status") == "paid":
            update_fields["purchases_amount"] = F("purchases_amount") + money(sale_order.get("total"))
            update_fields["total_sales_count"] = F("total_sales_count") + 1
        commonQuery.branchScopedQueryset(Customer, {"id": customer_id}, request).update(**update_fields)

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

    @staticmethod
    def finalizePaidSale(sale_order, customer, settings, request):
        if not customer:
            return {"customer": None, "reward": None}

        commonQuery.branchScopedQueryset(Customer, {"id": customer["id"]}, request).update(
            purchases_amount=F("purchases_amount") + money(sale_order.get("total")),
            total_sales_count=F("total_sales_count") + 1,
        )
        updated_customer = commonQuery.findOneRecord(
            Customer,
            customer["id"],
            request=request,
            tenant_config=True,
        )
        reward = SaleRewardService.processRewards(sale_order, request) if settings.enable_customer_rewards else None
        return {"customer": updated_customer, "reward": reward}


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
            product_id = SaleStockService.resolveBarcodeItem(item, request)
            product = commonQuery.findOneRecord(
                Product,
                product_id,
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
                    "counted",
                ],
            },
            request=request,
            tenant_config=True,
        )
        for applied in applied_coupons:
            if not applied.get("counted"):
                continue
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
            commonQuery.updateRecordById(
                OrdersCoupon,
                applied["id"],
                {"counted": False},
                request=request,
                tenant_config=True,
            )

    @staticmethod
    def trackOrderCoupons(sale_order_id, request):
        if not sale_order_id:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Sale order id is required to track coupons.")
        applied_coupons = commonQuery.findAllRecords(
            OrdersCoupon,
            {"sale_order_id": sale_order_id, "counted": False},
            {
                "attributes": [
                    "id",
                    "customer_coupon_id",
                    "name",
                ],
            },
            request=request,
            tenant_config=True,
        )
        for applied in applied_coupons:
            customer_coupon_id = applied.get("customer_coupon_id")
            if not customer_coupon_id:
                commonQuery.updateRecordById(
                    OrdersCoupon,
                    applied["id"],
                    {"counted": True},
                    request=request,
                    tenant_config=True,
                )
                continue
            issued_coupon = commonQuery.findOneRecord(
                CustomerCoupon,
                customer_coupon_id,
                request=request,
                tenant_config=True,
            )
            if issued_coupon is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, f"Customer coupon reference not found for {applied.get('name')}.")
            usage_count = int(issued_coupon.get("usage") or 0) + 1
            update_data = {"usage": usage_count}
            limit_usage = int(issued_coupon.get("limit_usage") or 0)
            if limit_usage > 0 and usage_count >= limit_usage:
                update_data["status"] = 1
            commonQuery.updateRecordById(
                CustomerCoupon,
                customer_coupon_id,
                update_data,
                request=request,
                tenant_config=True,
            )
            commonQuery.updateRecordById(
                OrdersCoupon,
                applied["id"],
                {"counted": True},
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
        if sale_order.get("payment_status") not in ["paid", "partially_paid"]:
            return

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
        paid_amount = max(money(sale_order.get("tendered_amount")) - money(sale_order.get("change_amount")), Decimal("0"))
        next_purchases_amount = max(money(customer.get("purchases_amount")) - paid_amount, Decimal("0"))
        next_total_sales_count = max(int(customer.get("total_sales_count") or 0) - 1, 0)
        next_owed_amount = max(money(customer.get("owed_amount")) - due_amount, Decimal("0"))

        commonQuery.updateRecordById(
            Customer,
            customer_id,
            {
                "purchases_amount": next_purchases_amount,
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
        if sale_order.get("payment_status") == "order_void":
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
    def computeRefundTax(sale_order, sale_item, refund_qty, line_total):
        original_qty = quantity(sale_item.get("quantity"))
        item_tax = money(sale_item.get("tax_amount"))
        if original_qty > 0 and item_tax > 0:
            return (item_tax / original_qty) * refund_qty

        order_tax = money(sale_order.get("tax_amount")) - money(sale_order.get("products_tax_value"))
        order_base = money(sale_order.get("total_without_tax"))
        if order_tax > 0 and order_base > 0:
            return (order_tax / order_base) * line_total
        return Decimal("0")

    @staticmethod
    def validateItems(sale_order, items, request):
        if not items:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one return item is required.")

        prepared_items = []
        total_refund = Decimal("0")
        total_tax = Decimal("0")

        for item in items or []:
            sale_item = SaleReturnValidationService.ensureSaleItem(sale_order["id"], item.get("sale_item_id") or item.get("id"), request)
            refund_qty = quantity(item.get("quantity"))
            if refund_qty <= 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Refund quantity must be greater than 0.")

            refundable_qty = quantity(sale_item.get("quantity"))
            if refund_qty > refundable_qty:
                raise api_error(400, ErrorCodes.BAD_REQUEST, f"Refund quantity exceeds remaining refundable quantity for item {sale_item['id']}.")

            unit_price = money(item.get("unit_price") if item.get("unit_price") is not None else sale_item.get("unit_price"))
            original_unit_price = money(sale_item.get("unit_price"))
            if unit_price > original_unit_price:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Refund unit price cannot exceed original unit price.")

            line_total = refund_qty * unit_price
            line_tax = SaleReturnValidationService.computeRefundTax(sale_order, sale_item, refund_qty, line_total)

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
                    "note": item.get("note") or item.get("description") or "",
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
        CustomerAccountService.saveTransaction(
            customer["id"],
            "refund",
            amount,
            request=request,
            description=note or f"Refund for sale {sale_order['code']}",
            order_id=sale_order["id"],
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
            if not data.get("exchange_sale_id"):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Exchange sale is required.")
            if int(data.get("exchange_sale_id")) == int(sale_order.get("id")):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Exchange sale cannot be the same sale.")
            difference_amount = Decimal("0")
            exchange_sale = commonQuery.findOneRecord(
                Order,
                data["exchange_sale_id"],
                request=request,
                tenant_config=True,
            )
            if exchange_sale is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Exchange sale not found.")
            if exchange_sale.get("payment_status") == "order_void":
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Void sale cannot be used for exchange.")
            difference_amount = money(exchange_sale.get("total")) - total
            if difference_amount < 0:
                if not data.get("payment_type"):
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Refund payment type is required when exchange value is lower than return value.")
                total_to_refund = abs(difference_amount)
                payment_data = {**data, "return_type": "refund"}
                settlement = SaleRefundService.handleRefundSettlement(return_order, sale_order, customer, payment_data, total_to_refund, settings, request)
                return {"refund_payment": settlement["refund_payment"], "difference_amount": difference_amount}
            return {"refund_payment": None, "difference_amount": difference_amount}

        payment_type = PaymentTypeService.resolvePaymentType(data.get("payment_type"), request)
        shift = getCurrentRegisterContext(
            request,
            sale_order.get("register_id"),
            required=bool(settings.enable_cash_registers and payment_type == "cash-payment"),
        )
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
    def refreshOrder(sale_order_id, request):
        sale_order = commonQuery.findOneRecord(
            Order,
            sale_order_id,
            request=request,
            tenant_config=True,
        )
        if sale_order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Sale order not found.")
        if sale_order.get("payment_status") in ["hold", "order_void"]:
            return successResponse("Sale order skipped from refresh.", data=sale_order)

        items = commonQuery.findAllRecords(
            OrdersProduct,
            {"sale_order_id": sale_order_id},
            {
                "attributes": [
                    "quantity",
                    "total",
                    "tax_amount",
                    "cost_price",
                ]
            },
            request=request,
            tenant_config=True,
        )
        payments = commonQuery.findAllRecords(
            OrderPayment,
            {"sale_order_id": sale_order_id},
            {"attributes": ["value"]},
            request=request,
            tenant_config=True,
        )
        coupons = commonQuery.findAllRecords(
            OrdersCoupon,
            {"sale_order_id": sale_order_id},
            {"attributes": ["discount_amount"]},
            request=request,
            tenant_config=True,
        )
        refunds = commonQuery.findAllRecords(
            OrdersRefund,
            {"sale_order_id": sale_order_id},
            {"attributes": ["total"]},
            request=request,
            tenant_config=True,
        )

        subtotal = sum((money(item.get("total")) for item in items), Decimal("0"))
        products_tax_value = sum((money(item.get("tax_amount")) for item in items), Decimal("0"))
        order_tax_rows = commonQuery.findAllRecords(
            OrderTax,
            {"sale_order_id": sale_order_id},
            {"attributes": ["tax_id", "tax_name", "rate"]},
            request=request,
            tenant_config=True,
        )
        order_tax_amount = Decimal("0")
        if order_tax_rows and sale_order.get("tax_type"):
            taxable_amount = max(subtotal - money(sale_order.get("discount_amount")), Decimal("0"))
            order_tax_result = SaleTaxService.createOrderTaxes(
                sale_order_id,
                sale_order.get("tax_type"),
                [
                    {
                        "id": row.get("tax_id"),
                        "name": row.get("tax_name"),
                        "rate": row.get("rate"),
                    }
                    for row in order_tax_rows
                ],
                taxable_amount,
                request,
            )
            order_tax_amount = order_tax_result["total_tax"]
            if sale_order.get("tax_type") == "exclusive" and order_tax_amount > 0:
                subtotal += order_tax_amount
        tax_amount = products_tax_value + order_tax_amount
        total_cogs = sum((money(item.get("cost_price")) * quantity(item.get("quantity")) for item in items), Decimal("0"))
        coupon_total = sum((money(coupon.get("discount_amount")) for coupon in coupons), Decimal("0"))
        refunded_total = sum((money(refund.get("total")) for refund in refunds), Decimal("0"))
        total = max(
            subtotal
            - money(sale_order.get("discount_amount"))
            - coupon_total
            + money(sale_order.get("shipping")),
            Decimal("0"),
        )
        paid_amount = sum((money(payment.get("value")) for payment in payments), Decimal("0"))
        change_amount = max(paid_amount - total, Decimal("0"))
        due_amount = max(total - paid_amount, Decimal("0"))
        if total == 0 and refunded_total > 0:
            payment_status = "refunded"
        elif total > 0 and refunded_total > 0:
            payment_status = "partially_refunded"
        else:
            payment_status = "paid" if due_amount == 0 else ("partially_paid" if paid_amount > 0 else "unpaid")

        updated = commonQuery.updateRecordById(
            Order,
            sale_order_id,
            {
                "subtotal": subtotal,
                "tax_amount": tax_amount,
                "products_tax_value": products_tax_value,
                "total_with_tax": total,
                "total_without_tax": total - tax_amount,
                "total_coupons": coupon_total,
                "total_cogs": total_cogs,
                "total": total,
                "tendered_amount": paid_amount,
                "change_amount": change_amount,
                "payment_status": payment_status,
                "final_payment_date": timezone.now() if payment_status == "paid" else None,
            },
            request=request,
            tenant_config=True,
        )
        SaleDraftService.trackOrderCoupons(sale_order_id, request)
        return successResponse("Sale order refreshed successfully.", data=updated)

    @staticmethod
    def recomputeCustomerOwed(customer_id, request):
        if not customer_id:
            return None
        customer = commonQuery.findOneRecord(Customer, customer_id, request=request, tenant_config=True)
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        orders = commonQuery.branchScopedQueryset(
            Order,
            {"customer_id": customer_id, "payment_status__in": ["unpaid", "partially_paid"]},
            request,
        ).exclude(status=2).values("total", "tendered_amount", "change_amount")
        owed_amount = sum((saleDueAmount(order) for order in orders), Decimal("0"))
        commonQuery.updateRecordById(
            Customer,
            customer_id,
            {"owed_amount": owed_amount},
            request=request,
            tenant_config=True,
        )
        return commonQuery.findOneRecord(Customer, customer_id, request=request, tenant_config=True)

    @staticmethod
    def processCustomerOwedAndRewards(sale_order_id, request):
        sale_order = commonQuery.findOneRecord(Order, sale_order_id, request=request, tenant_config=True)
        if sale_order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Sale order not found.")
        customer = SaleService.recomputeCustomerOwed(sale_order.get("customer_id"), request) if sale_order.get("customer_id") else None
        reward = None
        if customer and sale_order.get("payment_status") == "paid":
            result = SaleCustomerService.finalizePaidSale(
                sale_order,
                customer,
                getOptionSettings(request.user),
                request,
            )
            customer = result["customer"]
            reward = result["reward"]
        return successResponse(
            "Customer owed amount processed successfully.",
            data={"customer": customer, "reward_processed": reward is not None, "reward": reward},
        )

    @staticmethod
    def increaseCashierStats(sale_order_id, request):
        sale_order = commonQuery.findOneRecord(Order, sale_order_id, request=request, tenant_config=True)
        if sale_order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Sale order not found.")
        if sale_order.get("payment_status") == "paid" and sale_order.get("user_id"):
            commonQuery.branchScopedQueryset(User, {"id": sale_order["user_id"]}, request).update(
                total_sales=F("total_sales") + money(sale_order.get("total")),
                total_sales_count=F("total_sales_count") + 1,
            )
        return successResponse("Cashier stats increased successfully.")

    @staticmethod
    def saveOrderSettings(sale_order_id, request):
        sale_order = commonQuery.findOneRecord(Order, sale_order_id, request=request, tenant_config=True)
        if sale_order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Sale order not found.")

        option_keys = [
            key
            for key, _default_value in DEFAULT_ORDER_SETTINGS
            if key not in ["order_type", "discount_type", "discount_value", "tax_type", "tax_group", "note_visibility"]
        ]
        option_rows = {
            option.key: option.value
            for option in commonQuery.branchScopedQueryset(
                Option,
                {"status": 0, "key__in": option_keys},
                request,
            )
        }
        settings_payload = [
            (
                key,
                SaleValidationService.orderSettingValue(key, sale_order, option_rows) or default_value,
            )
            for key, default_value in DEFAULT_ORDER_SETTINGS
        ]
        with transaction.atomic():
            commonQuery.branchScopedQueryset(OrderSetting, {"sale_order_id": sale_order_id}, request).delete()
            created = [
                commonQuery.createRecord(
                    OrderSetting,
                    {"sale_order_id": sale_order_id, "key": key, "value": value},
                    request=request,
                    tenant_config=True,
                )
                for key, value in settings_payload
            ]
        return successResponse("Order settings saved successfully.", data=created)

    @staticmethod
    def saveOrderAddresses(sale_order_id, data, request):
        address_map = {
            "billing": data.get("billing"),
            "shipping": data.get("shipping_address"),
        }
        created = []
        for address_type, address in address_map.items():
            if not address:
                continue
            payload = dict(address)
            has_value = any(str(payload.get(field) or "").strip() for field in [
                "first_name",
                "last_name",
                "phone",
                "address_1",
                "email",
                "address_2",
                "country",
                "city",
                "pobox",
                "company",
                "company_name",
            ])
            if not has_value:
                continue
            created.append(
                commonQuery.createRecord(
                    OrderAddress,
                    {
                        "sale_order_id": sale_order_id,
                        "type": address_type,
                        "first_name": payload.get("first_name") or "",
                        "last_name": payload.get("last_name") or "",
                        "phone": payload.get("phone") or "",
                        "address_1": payload.get("address_1") or "",
                        "email": payload.get("email") or "",
                        "address_2": payload.get("address_2") or "",
                        "country": payload.get("country") or "",
                        "city": payload.get("city") or "",
                        "pobox": payload.get("pobox") or "",
                        "company_name": payload.get("company") or payload.get("company_name") or "",
                    },
                    request=request,
                    tenant_config=True,
                )
            )
        return created

    @staticmethod
    def resolveInstalments(sale_order_id, request):
        sale_order = commonQuery.findOneRecord(Order, sale_order_id, request=request, tenant_config=True)
        if sale_order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Sale order not found.")
        if sale_order.get("payment_status") not in ["paid", "partially_paid"]:
            return successResponse("Sale has no instalments to resolve.", data={"updated_count": 0})

        today_start = timezone.localtime(timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59, microsecond=999999)
        with transaction.atomic():
            instalments = list(
                commonQuery.branchScopedQueryset(
                    OrderInstalment,
                    {
                        "sale_order_id": sale_order_id,
                        "paid": False,
                        "date__gte": today_start,
                        "date__lte": today_end,
                        "status": 0,
                    },
                    request,
                )
                .select_for_update()
                .order_by("date", "id")
            )
            if not instalments:
                return successResponse("Sale has no instalments to resolve.", data={"updated_count": 0})

            paid_instalments = sum(
                (
                    money(item.amount)
                    for item in commonQuery.branchScopedQueryset(
                        OrderInstalment,
                        {"sale_order_id": sale_order_id, "paid": True, "status": 0},
                        request,
                    )
                ),
                Decimal("0"),
            )
            payable_difference = money(sale_order.get("tendered_amount")) - paid_instalments
            updated_count = 0
            for instalment in instalments:
                amount = money(instalment.amount)
                if payable_difference - amount >= 0:
                    instalment.paid = True
                    instalment.save(update_fields=["paid"])
                    payable_difference -= amount
                    updated_count += 1
        return successResponse("Sale instalments resolved successfully.", data={"updated_count": updated_count})

    @staticmethod
    def uncountDeletedOrderForCashier(sale_order_id, request):
        sale_order = commonQuery.findOneRecord(Order, sale_order_id, request=request, tenant_config=True)
        if sale_order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Sale order not found.")
        if sale_order.get("payment_status") == "paid" and sale_order.get("user_id"):
            user = commonQuery.findOneRecord(
                User,
                sale_order["user_id"],
                request=request,
                tenant_config=True,
            )
            if user:
                commonQuery.updateRecordById(
                    User,
                    sale_order["user_id"],
                    {
                        "total_sales": max(money(user.get("total_sales")) - money(sale_order.get("total")), Decimal("0")),
                        "total_sales_count": max(int(user.get("total_sales_count") or 0) - 1, 0),
                    },
                    request=request,
                    tenant_config=True,
                )
        return successResponse("Cashier stats decreased successfully.")

    @staticmethod
    def uncountDeletedOrderForCustomer(sale_order_id, request):
        sale_order = commonQuery.findOneRecord(Order, sale_order_id, request=request, tenant_config=True)
        if sale_order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Sale order not found.")
        customer_id = sale_order.get("customer_id")
        if not customer_id:
            return successResponse("Sale has no customer to update.")

        customer = commonQuery.findOneRecord(Customer, customer_id, request=request, tenant_config=True)
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")

        payment_status = sale_order.get("payment_status")
        if payment_status == "paid":
            payload = {
                "purchases_amount": max(
                    money(customer.get("purchases_amount")) - money(sale_order.get("total")),
                    Decimal("0"),
                )
            }
        elif payment_status == "partially_paid":
            due_amount = saleDueAmount(sale_order)
            payload = {
                "purchases_amount": max(
                    money(customer.get("purchases_amount")) - money(sale_order.get("tendered_amount")),
                    Decimal("0"),
                ),
                "owed_amount": max(
                    money(customer.get("owed_amount")) - due_amount,
                    Decimal("0"),
                ),
            }
        else:
            due_amount = saleDueAmount(sale_order)
            payload = {
                "owed_amount": max(
                    money(customer.get("owed_amount")) - due_amount,
                    Decimal("0"),
                )
            }
        updated = commonQuery.updateRecordById(
            Customer,
            customer_id,
            payload,
            request=request,
            tenant_config=True,
        )
        return successResponse("Customer sale counters decreased successfully.", data=updated)

    @staticmethod
    def reduceCashierStatsFromRefund(return_order_id, request):
        refund = commonQuery.findOneRecord(OrdersRefund, return_order_id, request=request, tenant_config=True)
        if refund is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Refund not found.")
        sale_order = commonQuery.findOneRecord(Order, refund.get("sale_order_id"), request=request, tenant_config=True)
        if sale_order and sale_order.get("user_id"):
            user = commonQuery.findOneRecord(
                User,
                sale_order["user_id"],
                request=request,
                tenant_config=True,
            )
            if user:
                commonQuery.updateRecordById(
                    User,
                    sale_order["user_id"],
                    {"total_sales": max(money(user.get("total_sales")) - money(refund.get("total")), Decimal("0"))},
                    request=request,
                    tenant_config=True,
                )
        return successResponse("Cashier refund stats processed successfully.")

    @staticmethod
    def decreaseCustomerPurchasesFromRefund(return_order_id, request):
        refund = commonQuery.findOneRecord(OrdersRefund, return_order_id, request=request, tenant_config=True)
        if refund is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Refund not found.")
        sale_order = commonQuery.findOneRecord(Order, refund.get("sale_order_id"), request=request, tenant_config=True)
        customer_id = sale_order.get("customer_id") if sale_order else None
        if customer_id:
            customer = commonQuery.findOneRecord(Customer, customer_id, request=request, tenant_config=True)
            if customer:
                commonQuery.updateRecordById(
                    Customer,
                    customer_id,
                    {
                        "purchases_amount": max(money(customer.get("purchases_amount")) - money(refund.get("total")), Decimal("0")),
                    },
                    request=request,
                    tenant_config=True,
                )
        return successResponse("Customer purchases reduced successfully.")

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
                    "user__username",
                    "register_id",
                    "register__name",
                    "title",
                    "order_type",
                    "payment_status",
                    "delivery_status",
                    "subtotal",
                    "discount_amount",
                    "total_coupons",
                    "shipping",
                    "tax_amount",
                    "total",
                    "tendered_amount",
                    "change_amount",
                    "created_at",
                    "refunds_count",
                    "latest_refund_id",
                ],
                "order": ["-id"],
                "annotate": {
                    "refunds_count": Count("returns"),
                    "latest_refund_id": Subquery(
                        OrdersRefund.objects.filter(sale_order_id=OuterRef("pk"))
                        .order_by("-id")
                        .values("id")[:1]
                    ),
                },
            },
            request=request,
            tenant_config=True,
        )
        for item in result["items"]:
            item["author_username"] = item.pop("user__username", None)
        return successResponse("Sales retrieved successfully.", data=result)

    @staticmethod
    def listInstallments(data, request):
        data = data or {}
        page = max(int(data.get("page") or 1), 1)
        limit_value = data.get("limit")
        fetch_all = limit_value in ["all", "All"]
        limit = None if fetch_all else int(limit_value or 10)
        offset = 0 if fetch_all else (page - 1) * limit

        queryset = commonQuery.branchScopedQueryset(OrderInstalment, {}, request).select_related(
            "sale_order",
            "sale_order__customer",
        )

        search = str(data.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(sale_order__code__icontains=search)
                | Q(sale_order__customer__first_name__icontains=search)
                | Q(sale_order__customer__last_name__icontains=search)
                | Q(sale_order__customer__username__icontains=search)
                | Q(sale_order__customer__email__icontains=search)
            )

        start_date = data.get("startDate")
        end_date = data.get("endDate")
        if start_date:
            start_value = parse_datetime(start_date) if isinstance(start_date, str) else start_date
            if start_value:
                queryset = queryset.filter(date__gte=start_value)
        if end_date:
            end_value = parse_datetime(end_date) if isinstance(end_date, str) else end_date
            if end_value:
                queryset = queryset.filter(date__lte=end_value)

        sort_by = data.get("sortBy")
        sort_direction = data.get("sortDirection") or "descending"
        sortable_fields = ["amount", "date", "paid", "created_at"]
        if sort_by in sortable_fields:
            queryset = queryset.order_by(("-" if sort_direction == "descending" else "") + sort_by)
        else:
            queryset = queryset.order_by("-date", "-id")

        total = queryset.count()
        if not fetch_all:
            queryset = queryset[offset : offset + limit]

        items = []
        for installment in queryset:
            order = installment.sale_order
            customer = getattr(order, "customer", None)
            customer_name = (
                getattr(customer, "full_name", None)
                or " ".join(
                    part
                    for part in [
                        getattr(customer, "first_name", None),
                        getattr(customer, "last_name", None),
                    ]
                    if part
                )
                or getattr(customer, "username", None)
                or "Walk-in Customer"
            )
            items.append(
                jsonsafe(
                    {
                        "id": installment.id,
                        "order_id": order.id if order else None,
                        "order_code": order.code if order else None,
                        "customer": customer_name,
                        "amount": installment.amount,
                        "date": installment.date,
                        "paid": installment.paid,
                        "created_at": installment.created_at,
                    }
                )
            )

        return successResponse(
            "Instalments retrieved successfully.",
            data={
                "items": items,
                "total": total,
                "totals": {},
                "currentPage": 1 if fetch_all else page,
                "pageSize": total if fetch_all else limit,
                "totalPages": 1 if fetch_all else (total + (limit - 1)) // (limit or 1),
                "hasNextPage": False if fetch_all else (offset + limit) < total,
                "hasPreviousPage": False if fetch_all else page > 1,
                "appliedFilters": {
                    **data,
                    "searchFields": ["order_code", "customer"],
                    "sortableFields": sortable_fields,
                },
            },
        )

    @staticmethod
    def getOrders(data, request):
        if data and data.get("id"):
            return SaleService.getSale(data["id"], request)
        filters = dict(data or {})
        if "limit" in filters and "page" not in filters:
            filters["page"] = 1
        return SaleService.listSales(filters, request)

    @staticmethod
    def getOrderCollection(data, request):
        limit = data.get("limit") if data else None
        options = {
            "attributes": [
                "id",
                "code",
                "customer_id",
                "customer__full_name",
                "customer__email",
                "user_id",
                "register_id",
                "order_type",
                "payment_status",
                "delivery_status",
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
        }
        if limit:
            options["limit"] = limit
        orders = commonQuery.findAllRecords(
            Order,
            {},
            options,
            request=request,
            tenant_config=True,
        )
        for order in orders:
            if order.get("customer_id"):
                order["customer"] = {
                    "id": order.get("customer_id"),
                    "full_name": order.get("customer__full_name"),
                    "email": order.get("customer__email"),
                }
            else:
                order["customer"] = None
        return successResponse("Orders retrieved successfully.", data=orders)

    @staticmethod
    def getSupportedPayments(request):
        payment_types = commonQuery.findAllRecords(
            PaymentType,
            {"status": 0},
            {
                "attributes": ["id", "label", "identifier", "description", "priority"],
                "order": ["priority", "label"],
            },
            request=request,
            tenant_config=True,
        )
        for index, payment in enumerate(payment_types):
            payment["selected"] = index == 0
        return successResponse("Payment types retrieved successfully.", data=payment_types)

    @staticmethod
    def getOrderPaymentFields(request):
        settings = getOptionSettings(request.user)
        payment_types = commonQuery.findAllRecords(
            PaymentType,
            {"status": 0},
            {
                "attributes": ["id", "label", "identifier", "description", "priority"],
                "order": ["priority", "label"],
            },
            request=request,
            tenant_config=True,
        )
        payment_options = []
        for payment in payment_types:
            payment_options.append(
                {
                    **payment,
                    "value": payment["identifier"],
                    "label": payment["label"],
                }
            )

        fields = [
            {
                "type": "select",
                "label": "Select Payment",
                "name": "identifier",
                "options": payment_options,
                "description": "choose the payment type.",
                "validation": "required",
            }
        ]

        if getattr(settings, "enable_cash_registers", False):
            registers = commonQuery.findAllRecords(
                Register,
                {
                    "status": 0,
                    "register_status__in": [Register.STATUS_OPENED, Register.STATUS_INUSE],
                },
                {
                    "attributes": ["id", "name"],
                    "order": ["name"],
                },
                request=request,
                tenant_config=True,
            )
            fields.append(
                {
                    "type": "select",
                    "label": "Select Register",
                    "name": "register_id",
                    "disabled": len(registers) == 0,
                    "options": [{"value": register["id"], "label": register["name"]} for register in registers],
                    "description": "Choose a register.",
                    "validation": "required",
                }
            )
        return successResponse("Order payment fields retrieved successfully.", data=fields)

    @staticmethod
    def getOrderTypeOptions(settings=None):
        enabled_types = getattr(settings, "order_types", None) or ["takeaway", "delivery"]
        options = [
            {
                "identifier": "takeaway",
                "label": "Take Away",
                "icon": "/images/groceries.png",
                "selected": False,
            },
            {
                "identifier": "delivery",
                "label": "Delivery",
                "icon": "/images/delivery.png",
                "selected": False,
            },
        ]
        return [option for option in options if option["identifier"] in enabled_types]

    @staticmethod
    def getPosSession(request):
        settings = getOptionSettings(request.user)
        payment_types = SaleService.getSupportedPayments(request).data
        options = {
            "pos_printing_document": getattr(settings, "printing_document", "receipt"),
            "orders_allow_partial": yesNo(getattr(settings, "orders_allow_partial", getattr(settings, "allow_partial_orders", False))),
            "orders_allow_unpaid": yesNo(getattr(settings, "orders_allow_unpaid", False)),
            "pos_order_types": getattr(settings, "order_types", None) or ["takeaway", "delivery"],
            "pos_order_sms": yesNo(getattr(settings, "pos_order_sms", False)),
            "pos_sound_enabled": yesNo(getattr(settings, "pos_sound_enabled", True)),
            "pos_quick_product": yesNo(getattr(settings, "quick_product_enabled", False)),
            "pos_quick_product_default_unit": getattr(settings, "pos_quick_product_default_unit", "") or 0,
            "pos_preferred_price": getattr(settings, "pos_preferred_price", "net_prices"),
            "pos_unit_price_editable": yesNo(getattr(settings, "unit_price_editable", False)),
            "pos_printing_enabled_for": getattr(settings, "printing_enabled_for", "only_paid_orders"),
            "pos_registers_enabled": yesNo(getattr(settings, "enable_cash_registers", False)),
            "pos_idle_counter": getattr(settings, "pos_idle_counter", "disabled"),
            "pos_disbursement": getattr(settings, "pos_disbursement", "no"),
            "customers_default": getattr(settings, "customers_default", None) or False,
            "pos_vat": getattr(settings, "pos_vat", "disabled"),
            "pos_tax_group": getattr(settings, "pos_tax_group", None) or None,
            "pos_tax_type": getattr(settings, "pos_tax_type", None) or False,
            "pos_printing_gateway": getattr(settings, "printing_gateway", "default"),
            "pos_show_quantity": bool(getattr(settings, "show_quantity", False)),
            "pos_new_item_audio": getattr(settings, "pos_new_item_audio", ""),
            "pos_complete_sale_audio": getattr(settings, "pos_complete_sale_audio", ""),
            "pos_numpad": getattr(settings, "pos_numpad", "default"),
            "pos_allow_wholesale_price": bool(getattr(settings, "allow_wholesale_price", False)),
            "pos_allow_decimal_quantities": bool(getattr(settings, "allow_decimal_quantities", False)),
            "pos_force_autofocus": bool(getattr(settings, "force_autofocus", False)),
            "pos_action_permission_duration": getattr(settings, "pos_action_permission_duration", "5"),
            "pos_action_permission_restricted_features": getattr(settings, "pos_action_permission_restricted_features", []),
            "pos_action_permission_enabled": getattr(settings, "pos_action_permission_enabled", "no"),
            "pos_show_preview_pinned_products": bool(getattr(settings, "show_preview_pinned_products", False)),
            "pos_enable_pinned_products": bool(getattr(settings, "enable_pinned_products", False)),
            "pos_items_merge": bool(getattr(settings, "items_merge", False)),
            "pos_layout": getattr(settings, "pos_layout", "grocery_shop"),
            "pos_enable_reordering": bool(getattr(settings, "pos_enable_reordering", False)),
        }
        return successResponse(
            "POS session retrieved successfully.",
            data={
                "title": getattr(getattr(request.user, "company", None), "name", None) or "POS",
                "orderTypes": SaleService.getOrderTypeOptions(settings),
                "options": options,
                "urls": {
                    "sale_printing_url": "/orders/receipt/{id}",
                    "orders_url": "/orders",
                    "dashboard_url": "/dashboard",
                    "categories_url": "/catalog/categories",
                    "registers_url": "/registers",
                    "order_type_url": "/settings/business",
                },
                "paymentTypes": payment_types,
            },
        )

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
                    "unit_quantity_id",
                    "product_category_id",
                    "product_category__name",
                    "tax_group_id",
                    "tax_group__name",
                    "tax_type",
                    "quantity",
                    "unit_price",
                    "discount_amount",
                    "tax_amount",
                    "price_net",
                    "price_gross",
                    "total_price_net",
                    "total_price_gross",
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
            item["refundable_quantity"] = sold_qty

        sale_order["due_amount"] = saleDueAmount(sale_order)
        sale_order["total_items"] = len(items)
        sale_order["total_quantity"] = sum((quantity(item.get("quantity")) for item in items), Decimal("0"))

        addresses = commonQuery.findAllRecords(
            OrderAddress,
            {"sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "type",
                    "first_name",
                    "last_name",
                    "phone",
                    "address_1",
                    "email",
                    "address_2",
                    "country",
                    "city",
                    "pobox",
                    "company_name",
                ],
                "order": ["id"],
            },
            request=request,
            tenant_config=True,
        )
        addresses_map = {address["type"]: address for address in addresses}

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
        payments = normalizeOrderPayments(payments)
        payment_labels = {
            item["identifier"]: item["label"]
            for item in commonQuery.findAllRecords(
                PaymentType,
                {"status__in": [0, 1]},
                {"attributes": ["identifier", "label"]},
                request=request,
                tenant_config=True,
            )
        }
        for payment in payments:
            payment["label"] = payment_labels.get(payment.get("identifier"), payment.get("identifier"))

        taxes = commonQuery.findAllRecords(
            OrderTax,
            {"sale_order_id": sale_order_id},
            {
                "attributes": [
                    "id",
                    "tax_id",
                    "tax_name",
                    "rate",
                    "tax_value",
                ],
                "order": ["id"],
            },
            request=request,
            tenant_config=True,
        )

        order_settings = commonQuery.findAllRecords(
            OrderSetting,
            {"sale_order_id": sale_order_id},
            {
                "attributes": ["id", "key", "value"],
                "order": ["id"],
            },
            request=request,
            tenant_config=True,
        )
        settings_map = {setting["key"]: setting["value"] for setting in order_settings}

        cashier = None
        if sale_order.get("user_id"):
            cashier = commonQuery.findOneRecord(
                User,
                sale_order["user_id"],
                options={"attributes": ["id", "username", "full_name", "email"]},
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
        totals["due_amount"] = max(money(sale_order.get("total")) - totals["paid_amount"], Decimal("0"))

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
            "cashier": cashier,
            "items": items,
            "payments": payments,
            "addresses": addresses_map,
            "order_addresses": addresses,
            "taxes": taxes,
            "settings": order_settings,
            "settings_map": settings_map,
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
    def getOrderProducts(sale_order_id, request):
        sale_data = SaleService.buildSaleDetail(sale_order_id, request)
        return successResponse("Order products retrieved successfully.", data=sale_data.get("items") or [])

    @staticmethod
    def getOrderPayments(sale_order_id, request):
        sale_data = SaleService.buildSaleDetail(sale_order_id, request)
        return successResponse("Order payments retrieved successfully.", data=sale_data.get("payments") or [])

    @staticmethod
    def addProducts(sale_order_id, products, request):
        if not products:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one product is required.")
        with transaction.atomic():
            sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
            if sale_order.get("payment_status") in ["paid", "refunded", "partially_refunded", "order_void"]:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "This sale cannot be edited in its current status.")
            if commonQuery.findOneRecord(OrdersRefund, {"sale_order_id": sale_order_id}, request=request, tenant_config=True):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Returned sale cannot be edited.")
            settings = getOptionSettings(request.user)
            created = []
            for item in products:
                sale_item, _line_total, _item_qty = SaleStockService.applySaleItem(item, sale_order, settings, request)
                created.append(sale_item)
            SaleService.refreshOrder(sale_order_id, request)
            return successResponse("Order products added successfully.", data={"items": created, "order": SaleService.buildSaleDetail(sale_order_id, request)})

    @staticmethod
    def deleteOrderProduct(sale_order_id, product_id, request):
        with transaction.atomic():
            sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
            if sale_order.get("payment_status") in ["paid", "refunded", "partially_refunded", "order_void"]:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "This sale cannot be edited in its current status.")
            sale_item = commonQuery.findOneRecord(
                OrdersProduct,
                {"id": product_id, "sale_order_id": sale_order_id},
                request=request,
                tenant_config=True,
            )
            if sale_item is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Order product not found.")
            commonQuery.branchScopedQueryset(
                OrdersProduct,
                {"id": product_id, "sale_order_id": sale_order_id},
                request,
            ).delete()
            SaleService.refreshOrder(sale_order_id, request)
            return successResponse("Order product deleted successfully.", data=SaleService.buildSaleDetail(sale_order_id, request))

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
            "products_tax_value": sale_data.get("products_tax_value"),
            "tax_group_id": sale_data.get("tax_group_id"),
            "tax_type": sale_data.get("tax_type"),
            "total": sale_data.get("total"),
            "total_with_tax": sale_data.get("total_with_tax"),
            "total_without_tax": sale_data.get("total_without_tax"),
            "tendered_amount": sale_data.get("tendered_amount"),
            "change_amount": sale_data.get("change_amount"),
            "due_amount": saleDueAmount(sale_data),
            "cashier": sale_data.get("cashier"),
            "items": sale_data.get("items") or [],
            "payments": sale_data.get("payments") or [],
            "taxes": sale_data.get("taxes") or [],
            "settings": sale_data.get("settings") or [],
            "settings_map": sale_data.get("settings_map") or {},
            "applied_coupons": sale_data.get("applied_coupons") or [],
            "totals_summary": sale_data.get("totals_summary") or {},
        }
        return successResponse("Sale receipt retrieved successfully.", data=receipt)

    @staticmethod
    def getOrderReceipt(sale_order_id, request):
        receipt = SaleService.getReceipt(sale_order_id, request).data
        return successResponse(
            f"Order Receipt — {receipt['code']}",
            data=receipt,
        )

    @staticmethod
    def getOrderInvoice(sale_order_id, request):
        invoice = SaleService.buildSaleDetail(sale_order_id, request)
        invoice["paymentStatus"] = invoice.get("payment_status")
        invoice["deliveryStatus"] = invoice.get("delivery_status")
        return successResponse(
            f"Order Invoice — {invoice['code']}",
            data=invoice,
        )

    @staticmethod
    def getOrderPaymentReceipt(payment_id, request):
        payment = commonQuery.findOneRecord(
            OrderPayment,
            payment_id,
            request=request,
            tenant_config=True,
        )
        if payment is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Order payment not found.")
        order = SaleService.buildSaleDetail(payment["sale_order_id"], request)
        payment_types = {
            item["identifier"]: item["label"]
            for item in commonQuery.findAllRecords(
                PaymentType,
                {"status__in": [0, 1]},
                {"attributes": ["identifier", "label"]},
                request=request,
                tenant_config=True,
            )
        }
        payment["label"] = payment_types.get(payment.get("identifier"), payment.get("identifier"))
        return successResponse(
            f"Payment Receipt — {order['code']}",
            data={
                "payment": payment,
                "order": order,
                "paymentTypes": payment_types,
            },
        )

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
                "title": data.get("title") or "",
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
                    "title",
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
        if draft is None or draft.get("payment_status") != "hold":
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
    def heldCartExpirationDays(request):
        option = commonQuery.branchScopedQueryset(
            Option,
            {"key": "orders_quotation_expiration", "status__in": [0, 1]},
            request,
        ).first()
        if option is None or option.value in [None, "", "never"]:
            return None
        try:
            days = int(option.value)
        except (TypeError, ValueError):
            return None
        return days if days > 0 else None

    @staticmethod
    def clearExpiredHeldCarts(data, request):
        days = SaleService.heldCartExpirationDays(request)
        if days is None:
            return successResponse("Held cart expiration is disabled.", data={"deleted_count": 0})

        expires_before = timezone.now() - timezone.timedelta(days=days)
        queryset = commonQuery.branchScopedQueryset(
            Order,
            {"payment_status": "hold", "created_at__lt": expires_before, "status__in": [0, 1]},
            request,
        )
        deleted_count = queryset.update(status=2, deleted_at=timezone.now())
        if deleted_count:
            commonQuery.createRecord(
                Notification,
                {
                    "identifier": "clear_hold_orders",
                    "title": "Hold Order Cleared",
                    "description": f"{deleted_count} held order(s) were deleted because they expired.",
                    "url": "/sales",
                    "source": "system",
                    "status": 0,
                },
                request=request,
                tenant_config=True,
            )
        return successResponse("Expired held carts cleared successfully.", data={"deleted_count": deleted_count})

    @staticmethod
    def purgeOrderStorage(data, request):
        deleted_count, _ = commonQuery.branchScopedQueryset(OrderStorage, {}, request).delete()
        return successResponse("Order storage purged successfully.", data={"deleted_count": deleted_count})

    @staticmethod
    def notifyExpiredLaidAway(data, request):
        now = timezone.now()
        orders = commonQuery.branchScopedQueryset(
            Order,
            {
                "payment_status__in": ["partially_paid", "unpaid"],
                "final_payment_date__isnull": False,
                "final_payment_date__lt": now,
                "status__in": [0, 1],
            },
            request,
        )
        
        updated_count = 0
        for order in orders:
            if order.tendered_amount > 0:
                order.payment_status = "partially_due"
            else:
                order.payment_status = "due"
            order.save(update_fields=["payment_status"])
            updated_count += 1
            
        if updated_count:
            commonQuery.branchScopedQueryset(
                Notification,
                {"identifier": "due-orders-notifications"},
                request,
            ).delete()
            
            from apps.settings.services import NotificationService
            NotificationService.dispatchForRoleNamespaces(
                ["admin", "pos.store.administrator"],
                title="Unpaid Orders Turned Due",
                description=f"{updated_count} order(s) either unpaid or partially paid has turned due. This occurs if none has been completed before the expected payment date.",
                identifier="due-orders-notifications",
                url="/sales",
                source="system",
                request=request,
            )
            
        return successResponse("Expired layaway orders processed successfully.", data={"updated_count": updated_count})

    @staticmethod
    def enqueueTrackLaidAwayOrders(data, request):
        from apps.settings.services import JobQueueService

        job = JobQueueService.enqueue("track_laid_away_orders", data or {}, request=request)
        return successResponse("Track layaway orders job queued successfully.", data={"job_id": job.id})

    @staticmethod
    def enqueueClearExpiredHeldCarts(data, request):
        from apps.settings.services import JobQueueService

        job = JobQueueService.enqueue("clear_hold_orders", data or {}, request=request)
        return successResponse("Held cart cleanup queued successfully.", data={"job_id": job.id})

    @staticmethod
    def enqueuePurgeOrderStorage(data, request):
        from apps.settings.services import JobQueueService

        job = JobQueueService.enqueue("purge_order_storage", data or {}, request=request)
        return successResponse("Order storage purge queued successfully.", data={"job_id": job.id})

    @staticmethod
    def enqueueTrackOrderCoupons(sale_order_id, request):
        from apps.settings.services import JobQueueService

        job = JobQueueService.enqueue("track_order_coupons", {"sale_order_id": sale_order_id}, request=request)
        return successResponse("Order coupon tracking queued successfully.", data={"job_id": job.id})

    @staticmethod
    def requestFromJob(job):
        from apps.common.helpers import requestFromJobUser

        return requestFromJobUser(job)

    @staticmethod
    def jobHandlers():
        return {
            "clear_hold_orders": lambda data, job: SaleService.clearExpiredHeldCarts(data, SaleService.requestFromJob(job)),
            "purge_order_storage": lambda data, job: SaleService.purgeOrderStorage(data, SaleService.requestFromJob(job)),
            "track_laid_away_orders": lambda data, job: SaleService.notifyExpiredLaidAway(data, SaleService.requestFromJob(job)),
            "refresh_order": lambda data, job: SaleService.refreshOrder(
                data.get("sale_order_id") or data.get("order_id"),
                SaleService.requestFromJob(job),
            ),
            "track_order_coupons": lambda data, job: SaleDraftService.trackOrderCoupons(
                data.get("sale_order_id") or data.get("order_id"),
                SaleService.requestFromJob(job),
            ),
            "process_customer_owed_and_rewards": lambda data, job: SaleService.processCustomerOwedAndRewards(
                data.get("sale_order_id") or data.get("order_id"),
                SaleService.requestFromJob(job),
            ),
            "save_order_settings": lambda data, job: SaleService.saveOrderSettings(
                data.get("sale_order_id") or data.get("order_id"),
                SaleService.requestFromJob(job),
            ),
            "resolve_instalments": lambda data, job: SaleService.resolveInstalments(
                data.get("sale_order_id") or data.get("order_id"),
                SaleService.requestFromJob(job),
            ),
            "delete_sales": lambda data, job: SaleService.delete(
                {"ids": data.get("ids") or data.get("sale_order_ids") or data.get("order_ids") or data.get("sale_order_id") or data.get("order_id")},
                SaleService.requestFromJob(job),
            ),
            "increase_cashier_stats": lambda data, job: SaleService.increaseCashierStats(
                data.get("sale_order_id") or data.get("order_id"),
                SaleService.requestFromJob(job),
            ),
            "uncount_deleted_order_for_cashier": lambda data, job: SaleService.uncountDeletedOrderForCashier(
                data.get("sale_order_id") or data.get("order_id"),
                SaleService.requestFromJob(job),
            ),
            "uncount_deleted_order_for_customer": lambda data, job: SaleService.uncountDeletedOrderForCustomer(
                data.get("sale_order_id") or data.get("order_id"),
                SaleService.requestFromJob(job),
            ),
            "reduce_cashier_stats_from_refund": lambda data, job: SaleService.reduceCashierStatsFromRefund(
                data.get("return_order_id") or data.get("refund_id"),
                SaleService.requestFromJob(job),
            ),
            "decrease_customer_purchases_from_refund": lambda data, job: SaleService.decreaseCustomerPurchasesFromRefund(
                data.get("return_order_id") or data.get("refund_id"),
                SaleService.requestFromJob(job),
            ),
        }

    @staticmethod
    def create(data, request):
        if not data.get("items"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one sale item is required.")

        with transaction.atomic():
            settings = getOptionSettings(request.user)
            SaleValidationService.ensurePartialOrdersAllowedForInstalments(data, settings)
            shift = getCurrentRegisterContext(
                request,
                data.get("register_id"),
                required=bool(settings.enable_cash_registers),
            )
            customer = SaleValidationService.ensureCustomer(data.get("customer_id"), request)
            order_type = SaleValidationService.ensureOrderTypeAllowed(data.get("order_type"), settings)

            sale_code = buildCode(Order, "", data.get("code"), request) if data.get("code") else generateOrderCode(request)
            status_defaults = SaleValidationService.statusDefaultsForOrderType(order_type)
            sale_order = commonQuery.createRecord(
                Order,
                {
                    "customer_id": data.get("customer_id"),
                    "register_id": shift["register_id"] if shift else None,
                    "code": sale_code,
                    "title": data.get("title") or "",
                    "order_type": order_type,
                    "process_status": status_defaults["process_status"],
                    "delivery_status": status_defaults["delivery_status"],
                    "payment_status": "unpaid",
                    "discount_amount": data.get("discount_amount") or 0,
                    "discount_percentage": data.get("discount_percentage") or 0,
                    "total_coupons": data.get("total_coupons") or 0,
                    "shipping": data.get("shipping") or 0,
                    "shipping_type": data.get("shipping_type") or "",
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
                sale_item, line_total, item_qty = SaleStockService.applySaleItem(item, sale_order, settings, request)
                sale_items.append(sale_item)
                subtotal += line_total
                total_quantity += item_qty
                total_items += 1

            products_tax_value = sum((money(item.get("tax_amount")) for item in sale_items), Decimal("0"))
            order_tax_config = SaleTaxService.resolveOrderTaxConfig(data, settings, request)
            order_tax_result = {"total_tax": Decimal("0"), "taxes": []}
            if order_tax_config["taxes"]:
                taxable_amount = max(subtotal - money(data.get("discount_amount")), Decimal("0"))
                order_tax_result = SaleTaxService.createOrderTaxes(
                    sale_order["id"],
                    order_tax_config["tax_type"],
                    order_tax_config["taxes"],
                    taxable_amount,
                    request,
                )
                if order_tax_config["tax_type"] == "exclusive" and getattr(settings, "pos_preferred_price", "net_prices") == "net_prices":
                    subtotal += order_tax_result["total_tax"]
            total_tax_amount = products_tax_value + order_tax_result["total_tax"]

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
                    "total_with_tax": total,
                    "total_without_tax": total - total_tax_amount,
                    "tax_group_id": order_tax_config["tax_group_id"],
                    "tax_type": order_tax_config["tax_type"],
                    "tax_amount": total_tax_amount,
                    "products_tax_value": products_tax_value,
                    "tendered_amount": paid_amount,
                    "change_amount": change_amount,
                    "total_coupons": coupon_result["discount_amount"],
                    "payment_status": payment_status,
                    "final_payment_date": timezone.now() if due_amount == 0 else None,
                },
                request=request,
                tenant_config=True,
            )

            SaleService.saveOrderSettings(sale_order["id"], request)
            SaleService.saveOrderAddresses(sale_order["id"], data, request)
            SaleDraftService.trackOrderCoupons(sale_order["id"], request)
            SaleStockService.recordSaleStock(sale_order, request)
            if data.get("instalments"):
                SaleService.createInstallments(
                    sale_order["id"],
                    {
                        "lines": data.get("instalments") or [],
                        "total_installments": data.get("total_instalments") or len(data.get("instalments") or []),
                        "final_payment_date": data.get("final_payment_date"),
                        "payment_ids": payment_summary.get("payment_ids") or [],
                        "allow_paid_order": True,
                        "support_instalments": data.get("support_instalments", True),
                    },
                    request,
                )
            elif data.get("support_instalments") is False:
                commonQuery.updateRecordById(
                    Order,
                    sale_order["id"],
                    {
                        "support_instalments": False,
                        "total_instalments": data.get("total_instalments") or 0,
                        "final_payment_date": data.get("final_payment_date"),
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
            if payment_status == "paid":
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
            SaleService.resolveInstalments(sale_order["id"], request)

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
    def update(sale_order_id, data, request):
        if not data.get("items"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one sale item is required.")

        with transaction.atomic():
            sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
            if sale_order.get("payment_status") in ["paid", "refunded", "partially_refunded", "order_void"]:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "This sale cannot be edited in its current status.")
            if commonQuery.findOneRecord(
                OrdersRefund,
                {"sale_order_id": sale_order_id},
                request=request,
                tenant_config=True,
            ):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Returned sale cannot be edited.")

            settings = getOptionSettings(request.user)
            SaleValidationService.ensurePartialOrdersAllowedForInstalments(data, settings)
            shift = getCurrentRegisterContext(
                request,
                data.get("register_id") or sale_order.get("register_id"),
                required=bool(settings.enable_cash_registers),
            )
            customer = SaleValidationService.ensureCustomer(data.get("customer_id"), request)
            order_type = SaleValidationService.ensureOrderTypeAllowed(data.get("order_type"), settings)
            status_defaults = SaleValidationService.statusDefaultsForOrderType(order_type)

            preserved_payment_summary = OrderPaymentService.validatePreservedPayments(
                sale_order,
                data.get("payments") or [],
                request,
            )

            SaleDraftService.reverseAppliedCoupons(sale_order_id, request)
            SaleDraftService.reverseRewards(sale_order, request)
            SaleVoidService.reverseCustomerImpact(sale_order, request)
            SaleVoidService.restockSale(sale_order, request)
            AccountingService.deleteOrderTransactionsHistory(sale_order_id, request)

            commonQuery.branchScopedQueryset(OrdersProduct, {"sale_order_id": sale_order_id}, request).delete()
            commonQuery.branchScopedQueryset(OrderTax, {"sale_order_id": sale_order_id}, request).delete()
            commonQuery.branchScopedQueryset(OrdersCoupon, {"sale_order_id": sale_order_id}, request).delete()
            commonQuery.branchScopedQueryset(OrderInstalment, {"sale_order_id": sale_order_id}, request).delete()
            commonQuery.branchScopedQueryset(OrderSetting, {"sale_order_id": sale_order_id}, request).delete()
            commonQuery.branchScopedQueryset(OrderAddress, {"sale_order_id": sale_order_id}, request).delete()

            sale_order = commonQuery.updateRecordById(
                Order,
                sale_order_id,
                {
                    "customer_id": data.get("customer_id"),
                    "register_id": shift["register_id"] if shift else None,
                    "order_type": order_type,
                    "process_status": status_defaults["process_status"],
                    "delivery_status": status_defaults["delivery_status"],
                    "payment_status": "unpaid",
                    "discount_amount": data.get("discount_amount") or 0,
                    "discount_percentage": data.get("discount_percentage") or 0,
                    "total_coupons": data.get("total_coupons") or 0,
                    "shipping": data.get("shipping") or 0,
                    "shipping_type": data.get("shipping_type") or "",
                    "tax_amount": data.get("tax_amount") or 0,
                    "tendered_amount": preserved_payment_summary["paid_amount"],
                    "change_amount": 0,
                    "note": data.get("note") or "",
                    "final_payment_date": None,
                },
                request=request,
                tenant_config=True,
            )

            subtotal = Decimal("0")
            sale_items = []
            for item in data.get("items") or []:
                sale_item, line_total, _item_qty = SaleStockService.applySaleItem(item, sale_order, settings, request)
                sale_items.append(sale_item)
                subtotal += line_total

            products_tax_value = sum((money(item.get("tax_amount")) for item in sale_items), Decimal("0"))
            order_tax_config = SaleTaxService.resolveOrderTaxConfig(data, settings, request)
            order_tax_result = {"total_tax": Decimal("0"), "taxes": []}
            if order_tax_config["taxes"]:
                taxable_amount = max(subtotal - money(data.get("discount_amount")), Decimal("0"))
                order_tax_result = SaleTaxService.createOrderTaxes(
                    sale_order["id"],
                    order_tax_config["tax_type"],
                    order_tax_config["taxes"],
                    taxable_amount,
                    request,
                )
                if order_tax_config["tax_type"] == "exclusive" and getattr(settings, "pos_preferred_price", "net_prices") == "net_prices":
                    subtotal += order_tax_result["total_tax"]
            total_tax_amount = products_tax_value + order_tax_result["total_tax"]

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

            new_payment_summary = OrderPaymentService.applyPayments(
                sale_order,
                OrderPaymentService.splitNewPayments(data.get("payments") or []),
                shift,
                customer,
                settings,
                request,
            )
            paid_amount = preserved_payment_summary["paid_amount"] + new_payment_summary["paid_amount"]
            cash_paid_amount = preserved_payment_summary["cash_paid_amount"] + new_payment_summary["cash_paid_amount"]
            due_amount = max(total - paid_amount, Decimal("0"))
            change_amount = max(paid_amount - total, Decimal("0"))
            SaleValidationService.ensureCashChangeSupported(change_amount, cash_paid_amount)
            SaleValidationService.ensurePaymentRules(
                total,
                paid_amount,
                due_amount,
                customer,
                settings,
                request,
            )

            payment_status = "paid" if due_amount == 0 else ("partially_paid" if paid_amount > 0 else "unpaid")
            updated_sale = commonQuery.updateRecordById(
                Order,
                sale_order_id,
                {
                    "subtotal": subtotal,
                    "total": total,
                    "total_with_tax": total,
                    "total_without_tax": total - total_tax_amount,
                    "tax_group_id": order_tax_config["tax_group_id"],
                    "tax_type": order_tax_config["tax_type"],
                    "tax_amount": total_tax_amount,
                    "products_tax_value": products_tax_value,
                    "tendered_amount": paid_amount,
                    "change_amount": change_amount,
                    "total_coupons": coupon_result["discount_amount"],
                    "payment_status": payment_status,
                    "final_payment_date": timezone.now() if due_amount == 0 else None,
                },
                request=request,
                tenant_config=True,
            )

            if shift and change_amount > 0 and cash_paid_amount > 0:
                RegisterService.deleteRegisterHistoryUsingOrder(sale_order_id, request)
                for payment in OrderPaymentService.existingPayments(sale_order_id, request):
                    if payment.get("identifier") == "cash-payment":
                        RegisterService.recordOrderPayment(payment["id"], request)
                SaleRegisterService.recordChangeGiven(updated_sale, shift, change_amount, request)

            SaleService.saveOrderSettings(updated_sale["id"], request)
            SaleService.saveOrderAddresses(updated_sale["id"], data, request)
            SaleDraftService.trackOrderCoupons(updated_sale["id"], request)
            SaleStockService.recordSaleStock(updated_sale, request)
            updated_customer = SaleCustomerService.applyCustomerImpact(updated_sale, request)
            reward = SaleRewardService.processRewards(updated_sale, request) if settings.enable_customer_rewards else None
            AccountingService.reflectEvent(
                "order_unpaid",
                total,
                name=f"Order {updated_sale['code']}",
                transaction_type="income",
                source_type="sale",
                source_id=updated_sale["id"],
                transaction_date=timezone.now(),
                description=updated_sale.get("note") or "Sale updated",
                reference_number=updated_sale["code"],
                request=request,
            )
            if paid_amount > 0:
                AccountingService.reflectEvent(
                    "order_from_unpaid_to_paid",
                    min(paid_amount, total),
                    name=f"Order payment {updated_sale['code']}",
                    transaction_type="income",
                    source_type="sale",
                    source_id=updated_sale["id"],
                    transaction_date=timezone.now(),
                    description="Sale payment received",
                    reference_number=updated_sale["code"],
                    request=request,
                )
            if payment_status == "paid":
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
                    name=f"Order COGS {updated_sale['code']}",
                    transaction_type="expense",
                    source_type="sale",
                    source_id=updated_sale["id"],
                    transaction_date=timezone.now(),
                    description="Cost of goods sold",
                    reference_number=updated_sale["code"],
                    request=request,
                )
            SaleService.resolveInstalments(updated_sale["id"], request)
            ReportService.recomputeDashboardRange({}, request)

            return successResponse(
                "Sale updated successfully.",
                data={
                    **updated_sale,
                    "items": sale_items,
                    "applied_coupons": coupon_result["applied_coupons"],
                    "customer": updated_customer,
                    "reward": reward,
                    "paid_amount": paid_amount,
                },
            )

    @staticmethod
    def void(sale_order_id, data, request):
        with transaction.atomic():
            sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
            if sale_order.get("payment_status") == "order_void":
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
                    "payment_status": "order_void",
                    "voidance_reason": data.get("note") or data.get("reason") or sale_order.get("voidance_reason"),
                    "note": (sale_order.get("note") or "") + (
                        f"\nVoid Note: {data.get('note')}" if data.get("note") else ""
                    ),
                },
                request=request,
                tenant_config=True,
            )
            AccountingService.reflectEvent(
                "order_paid_voided" if paid_amount > 0 else "order_unpaid_voided",
                paid_amount if paid_amount > 0 else sale_order.get("total"),
                name=f"Voided order {sale_order['code']}",
                transaction_type="adjustment",
                source_type="sale",
                source_id=sale_order_id,
                transaction_date=timezone.now(),
                description=data.get("note") or ("Paid sale voided" if paid_amount > 0 else "Unpaid sale voided"),
                reference_number=sale_order["code"],
                request=request,
            )
            DomainActionService.afterSaleVoided(sale_order, request)
            return successResponse("The order has been correctly voided.", data=updated)

    @staticmethod
    def voidOrder(sale_order_id, data, request):
        sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        commonQuery.updateRecordById(
            Order,
            sale_order_id,
            {
                "payment_status": "order_void",
                "voidance_reason": data.get("reason") or data.get("note") or sale_order.get("voidance_reason"),
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("The order has been correctly voided.")

    @staticmethod
    def printOrder(sale_order_id, doc, request):
        SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        return successResponse("The printing event has been successfully dispatched.")

    @staticmethod
    def normalizeOrderRefundPayload(data):
        normalized = dict(data or {})
        if normalized.get("products") and not normalized.get("items"):
            normalized["items"] = normalized["products"]
        payment = normalized.get("payment") or {}
        if payment.get("identifier") and not normalized.get("payment_type"):
            normalized["payment_type"] = payment["identifier"]
        normalized.setdefault("return_type", "refund")
        return normalized

    @staticmethod
    def refundOrder(sale_order_id, data, request):
        normalized = SaleService.normalizeOrderRefundPayload(data)
        result = SaleService.createReturn(sale_order_id, normalized, request)
        result_data = result.data or {}
        created_items = result_data.get("items") or []
        results = []
        for item in created_items:
            order_product = commonQuery.findOneRecord(
                OrdersProduct,
                item.get("sale_item_id"),
                request=request,
                tenant_config=True,
            )
            results.append(
                {
                    "status": "success",
                    "message": f"The product {order_product.get('name') if order_product else item.get('sale_item_id')} has been successfully refunded.",
                    "data": {
                        "productRefund": item,
                        "orderProduct": order_product,
                    },
                }
            )
        return successResponse(
            "The order has been successfully refunded.",
            data={
                "results": results,
                "order": result_data.get("sale_order"),
                "orderRefund": result_data.get("return_order"),
            },
        )

    @staticmethod
    def getOrderRefunds(sale_order_id, request):
        order = SaleService.buildSaleDetail(sale_order_id, request)
        order["refunds"] = SaleService.getRefunds(sale_order_id, request).data
        return successResponse("Order refunds retrieved successfully.", data=order)

    @staticmethod
    def delete(data, request):
        ids = data.get("ids")
        if not isinstance(ids, list):
            ids = [ids]
        deleted_count = 0
        for sale_order_id in ids:
            with transaction.atomic():
                sale_order = commonQuery.findOneRecord(Order, sale_order_id, request=request, tenant_config=True)
                if sale_order is None:
                    continue

                AccountingService.deleteOrderTransactionsHistory(sale_order_id, request)
                commonQuery.branchScopedQueryset(OrderSetting, {"sale_order_id": sale_order_id}, request).delete()
                SaleDraftService.reverseAppliedCoupons(sale_order_id, request)
                SaleDraftService.reverseRewards(sale_order, request)

                if sale_order.get("payment_status") != "order_void":
                    sale_items = commonQuery.findAllRecords(
                        OrdersProduct,
                        {"sale_order_id": sale_order_id},
                        {
                            "attributes": [
                                "id",
                                "product_id",
                                "unit_id",
                                "quantity",
                                "unit_price",
                                "total",
                                "item_status",
                            ]
                        },
                        request=request,
                        tenant_config=True,
                    )
                    for item in sale_items:
                        if item.get("product_id") and sale_order.get("payment_status") in [
                            "paid",
                            "partially_paid",
                            "unpaid",
                            "partially_due",
                            "partially_refunded",
                        ]:
                            ProductStockService.recordStockHistory(
                                ProductHistory.ACTION_RETURNED,
                                {
                                    "product_id": item["product_id"],
                                    "order_id": sale_order_id,
                                    "order_product_id": item["id"],
                                    "quantity": item.get("quantity"),
                                    "unit_id": item.get("unit_id"),
                                    "unit_price": item.get("unit_price") or 0,
                                    "total_price": item.get("total") or 0,
                                    "description": f"Sale deleted {sale_order.get('code')}",
                                },
                                request,
                            )

                commonQuery.branchScopedQueryset(OrdersProduct, {"sale_order_id": sale_order_id}, request).delete()
                commonQuery.branchScopedQueryset(OrderPayment, {"sale_order_id": sale_order_id}, request).delete()
                commonQuery.branchScopedQueryset(OrderTax, {"sale_order_id": sale_order_id}, request).delete()
                commonQuery.branchScopedQueryset(OrdersCoupon, {"sale_order_id": sale_order_id}, request).delete()
                commonQuery.branchScopedQueryset(OrderInstalment, {"sale_order_id": sale_order_id}, request).delete()
                commonQuery.branchScopedQueryset(OrderAddress, {"sale_order_id": sale_order_id}, request).delete()
                RegisterService.deleteRegisterHistoryUsingOrder(sale_order_id, request)
                SaleService.uncountDeletedOrderForCashier(sale_order_id, request)
                SaleService.uncountDeletedOrderForCustomer(sale_order_id, request)
                deleted_count += commonQuery.hardDeleteRecords(Order, sale_order_id, request=request, tenant_config=True)[0]
                ReportService.recomputeDashboardRange({}, request)

        if deleted_count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Sale order not found.")
        return successResponse("The order has been deleted.", data={"deleted_count": deleted_count})

    @staticmethod
    def collectDue(sale_order_id, data, request):
        with transaction.atomic():
            sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
            if sale_order.get("payment_status") in ["order_void", "refunded"]:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Due cannot be collected for this sale.")

            remaining_due = saleDueAmount(sale_order)
            if remaining_due <= 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "This sale does not have any due amount.")
            if not data.get("payments"):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one payment is required.")

            settings = getOptionSettings(request.user)
            SaleValidationService.ensureStrictInstallmentPaymentAllowed(sale_order, settings, request)
            shift = getCurrentRegisterContext(
                request,
                sale_order.get("register_id"),
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
            SaleValidationService.ensurePartialDuePaymentAllowed(collected_amount, remaining_due, settings)

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

            SaleStockService.recordSaleStock(updated_sale, request)
            if sale_order.get("payment_status") != "paid" and next_status == "paid":
                DomainActionService.afterSalePaid(updated_sale, request)
                SaleCustomerService.finalizePaidSale(updated_sale, customer, settings, request)
                sale_items = commonQuery.findAllRecords(
                    OrdersProduct,
                    {"sale_order_id": sale_order_id},
                    {"attributes": ["quantity", "cost_price"]},
                    request=request,
                    tenant_config=True,
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
                    source_id=sale_order_id,
                    transaction_date=timezone.now(),
                    description="Cost of goods sold",
                    reference_number=sale_order["code"],
                    request=request,
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
    def addPayment(sale_order_id, data, request):
        sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        if sale_order.get("payment_status") == "paid":
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unable to proceed as the order is already paid.")

        amount = money(data.get("amount") if data.get("amount") is not None else data.get("value"))
        if amount <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment amount must be greater than 0.")
        payment_type = PaymentTypeService.resolvePaymentType(data.get("payment_type") or data.get("identifier"), request)

        with transaction.atomic():
            settings = getOptionSettings(request.user)
            shift = getCurrentRegisterContext(
                request,
                data.get("register_id") or sale_order.get("register_id"),
                required=bool(settings.enable_cash_registers and payment_type == "cash-payment"),
            )
            customer = SaleValidationService.ensureCustomer(sale_order.get("customer_id"), request)
            payment_summary = OrderPaymentService.collectDuePayments(
                sale_order,
                [
                    {
                        "payment_type": payment_type,
                        "amount": amount,
                        "reference_number": data.get("reference_number") or "",
                        "note": data.get("note") or "",
                    }
                ],
                shift,
                customer,
                settings,
                request,
            )
            paid_amount = payment_summary["paid_amount"]
            next_tendered = money(sale_order.get("tendered_amount")) + paid_amount
            total = money(sale_order.get("total"))
            next_due = max(total - next_tendered, Decimal("0"))
            SaleValidationService.ensurePartialDuePaymentAllowed(paid_amount, saleDueAmount(sale_order), settings)
            updated_sale = commonQuery.updateRecordById(
                Order,
                sale_order_id,
                {
                    "register_id": data.get("register_id") or sale_order.get("register_id"),
                    "tendered_amount": next_tendered,
                    "change_amount": max(next_tendered - total, Decimal("0")),
                    "payment_status": "paid" if next_due == 0 else "partially_paid",
                    "final_payment_date": timezone.now() if next_due == 0 else sale_order.get("final_payment_date"),
                },
                request=request,
                tenant_config=True,
            )

            SaleStockService.recordSaleStock(updated_sale, request)
            if sale_order.get("payment_status") != "paid" and next_due == 0:
                DomainActionService.afterSalePaid(updated_sale, request)
                SaleCustomerService.finalizePaidSale(updated_sale, customer, settings, request)
            if customer and paid_amount > 0:
                next_owed_amount = max(money(customer.get("owed_amount")) - min(paid_amount, saleDueAmount(sale_order)), Decimal("0"))
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
                        "amount": paid_amount,
                        "previous_amount": customer.get("owed_amount"),
                        "next_amount": next_owed_amount,
                        "operation": "payment",
                        "order_id": sale_order_id,
                        "description": data.get("note") or f"Payment for sale {sale_order['code']}",
                    },
                    request=request,
                    tenant_config=True,
                )

            AccountingService.reflectEvent(
                "order_from_unpaid_to_paid",
                min(paid_amount, total),
                name=f"Order payment {sale_order['code']}",
                transaction_type="income",
                source_type="sale",
                source_id=sale_order_id,
                transaction_date=timezone.now(),
                description=data.get("note") or "Sale payment received",
                reference_number=sale_order["code"],
                request=request,
            )
            refreshed_sale = SaleService.buildSaleDetail(sale_order_id, request)
            return successResponse(
                "The payment has been saved.",
                data={
                    "payment": data,
                    "orderPayment": {"id": (payment_summary.get("payment_ids") or [None])[0]},
                    "order": refreshed_sale,
                },
            )

    @staticmethod
    def updateProcessingStatus(sale_order_id, data, request):
        sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        status = SaleValidationService.ensureProcessingStatusAllowed(data.get("status"), sale_order)
        updated = commonQuery.updateRecordById(
            Order,
            sale_order_id,
            {
                "process_status": status,
                "note": data.get("note") or sale_order.get("note") or "",
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Processing status updated successfully.", data=updated)

    @staticmethod
    def updateDeliveryStatus(sale_order_id, data, request):
        sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        status = SaleValidationService.ensureDeliveryStatusAllowed(data.get("status"), sale_order)
        updated = commonQuery.updateRecordById(
            Order,
            sale_order_id,
            {
                "delivery_status": status,
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
        settings = getOptionSettings(request.user)
        lines = data.get("lines") or []
        payment_ids = data.get("payment_ids") or []
        if data.get("instalment"):
            lines = [data["instalment"]]
        if not lines:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one installment line is required.")
        if not getattr(settings, "orders_allow_partial", False):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Partially paid orders are disabled.")
        if saleDueAmount(sale_order) <= 0 and not data.get("allow_paid_order"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Installments can be created only when due amount exists.")

        with transaction.atomic():
            commonQuery.branchScopedQueryset(OrderInstalment, {"sale_order_id": sale_order_id}, request).delete()
            payments_by_amount = {}
            if payment_ids:
                payments = commonQuery.branchScopedQueryset(
                    OrderPayment,
                    {"id__in": payment_ids, "sale_order_id": sale_order_id},
                    request,
                ).order_by("id")
                for payment in payments:
                    payments_by_amount.setdefault(money(payment.value), []).append(payment)
            used_payment_ids = set()

            for line in lines:
                paid = bool(line.get("paid"))
                payment_id = None
                if paid:
                    for payment in payments_by_amount.get(money(line.get("amount") or 0), []):
                        if payment.id not in used_payment_ids:
                            payment_id = payment.id
                            used_payment_ids.add(payment.id)
                            break
                commonQuery.createRecord(
                    OrderInstalment,
                    {
                        "sale_order_id": sale_order_id,
                        "date": parseInstallmentDate(line.get("date") or line.get("due_date")),
                        "amount": line.get("amount") or 0,
                        "paid": paid,
                        "payment_id": payment_id,
                    },
                    request=request,
                    tenant_config=True,
                )

            commonQuery.updateRecordById(
                Order,
                sale_order_id,
                {
                    "support_instalments": data.get("support_instalments", True),
                    "total_instalments": data.get("total_installments") or len(lines),
                    "final_payment_date": data.get("final_payment_date") or None,
                },
                request=request,
                tenant_config=True,
            )
            sale_data = SaleService.buildSaleDetail(sale_order_id, request)
            return successResponse("Instalments saved successfully.", data=sale_data.get("instalments"))

    @staticmethod
    def createInstallment(sale_order_id, data, request):
        sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        amount = money(data.get("amount"))
        due_date = parseInstallmentDate(data.get("date") or data.get("due_date"))
        if amount <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "The defined amount is not valid.")
        existing_total = sum(
            (
                money(item.amount)
                for item in commonQuery.branchScopedQueryset(
                    OrderInstalment,
                    {"sale_order_id": sale_order_id, "status": 0},
                    request,
                )
            ),
            Decimal("0"),
        )
        if existing_total >= money(sale_order.get("total")):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "No further instalments is allowed for this order. The total instalment already covers the order total.")
        installment = commonQuery.createRecord(
            OrderInstalment,
            {
                "sale_order_id": sale_order_id,
                "date": due_date,
                "amount": amount,
                "paid": False,
            },
            request=request,
            tenant_config=True,
        )
        total_instalments = commonQuery.branchScopedQueryset(
            OrderInstalment,
            {"sale_order_id": sale_order_id, "status": 0},
            request,
        ).count()
        commonQuery.updateRecordById(
            Order,
            sale_order_id,
            {"total_instalments": total_instalments, "support_instalments": True},
            request=request,
            tenant_config=True,
        )
        return successResponse("The instalment has been created.", data={"instalment": installment})

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
        if installment.get("paid"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Paid installment cannot be edited.")
        update_data = dict(data or {})
        if update_data.get("instalment"):
            update_data = dict(update_data["instalment"])
        if "due_date" in update_data:
            update_data["date"] = update_data.pop("due_date")
        if "date" in update_data:
            update_data["date"] = parseInstallmentDate(update_data["date"])
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
        commonQuery.branchScopedQueryset(
            OrderInstalment,
            {"id": installment_id, "sale_order_id": sale_order_id},
            request,
        ).delete()
        return successResponse("Installment deleted successfully.")

    @staticmethod
    def payInstallment(sale_order_id, installment_id, data, request):
        sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
        if sale_order.get("payment_status") == "paid":
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unable to proceed as the order is already paid.")
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

        amount = money(data.get("amount") if data.get("amount") is not None else installment.get("amount"))
        if amount <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Installment amount must be greater than 0.")
        if amount != money(installment.get("amount")):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Installment payment must match the installment amount.")

        with transaction.atomic():
            settings = getOptionSettings(request.user)
            SaleValidationService.ensureStrictInstallmentPaymentAllowed(sale_order, settings, request)
            shift = getCurrentRegisterContext(
                request,
                sale_order.get("register_id"),
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

            SaleValidationService.ensurePartialDuePaymentAllowed(amount, saleDueAmount(sale_order), settings)
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
            next_status = "paid" if next_due == 0 else "partially_paid"
            updated_sale = commonQuery.updateRecordById(
                Order,
                sale_order_id,
                {
                    "tendered_amount": next_tendered,
                    "payment_status": next_status,
                    "final_payment_date": timezone.now() if next_due == 0 else sale_order.get("final_payment_date"),
                },
                request=request,
                tenant_config=True,
            )
            SaleStockService.recordSaleStock(updated_sale, request)
            if sale_order.get("payment_status") != "paid" and next_status == "paid":
                DomainActionService.afterSalePaid(updated_sale, request)
                SaleCustomerService.finalizePaidSale(updated_sale, customer, settings, request)
                sale_items = commonQuery.findAllRecords(
                    OrdersProduct,
                    {"sale_order_id": sale_order_id},
                    {"attributes": ["quantity", "cost_price"]},
                    request=request,
                    tenant_config=True,
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
                    source_id=sale_order_id,
                    transaction_date=timezone.now(),
                    description="Cost of goods sold",
                    reference_number=sale_order["code"],
                    request=request,
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
            updated_instalment = commonQuery.findOneRecord(
                OrderInstalment,
                installment_id,
                request=request,
                tenant_config=True,
            )
            return successResponse(
                "The instalment has been saved.",
                data={
                    "instalment": updated_instalment,
                    "payment": {"id": (payment_summary.get("payment_ids") or [None])[0]},
                    "order": refreshed_sale,
                },
            )

    @staticmethod
    def createReturn(sale_order_id, data, request):
        SaleReturnValidationService.ensureReturnType(data.get("return_type") or "refund")

        with transaction.atomic():
            sale_order = SaleReturnValidationService.ensureSaleOrder(sale_order_id, request)
            settings = getOptionSettings(request.user)
            customer = SaleValidationService.ensureCustomer(sale_order.get("customer_id"), request) if sale_order.get("customer_id") else None
            prepared = SaleReturnValidationService.validateItems(sale_order, data.get("items") or [], request)
            shipping_refund = money(sale_order.get("shipping")) if data.get("refund_shipping") else Decimal("0")
            refund_total = prepared["total"] + shipping_refund

            return_order = commonQuery.createRecord(
                OrdersRefund,
                {
                    "sale_order_id": sale_order["id"],
                    "tax_amount": prepared["tax_amount"],
                    "shipping": shipping_refund,
                    "total": refund_total,
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

                remaining_qty = max(quantity(item["sale_item"].get("quantity")) - item["quantity"], Decimal("0"))
                original_qty = quantity(item["sale_item"].get("quantity"))
                tax_ratio = money(item["sale_item"].get("tax_amount")) / original_qty if original_qty > 0 else Decimal("0")
                next_tax_amount = tax_ratio * remaining_qty
                next_total = remaining_qty * money(item["sale_item"].get("unit_price")) + next_tax_amount
                item_status = "returned" if remaining_qty <= 0 else "partially_returned"
                commonQuery.updateRecordById(
                    OrdersProduct,
                    item["sale_item"]["id"],
                    {
                        "quantity": remaining_qty,
                        "tax_amount": next_tax_amount,
                        "total": next_total,
                        "item_status": item_status,
                    },
                    request=request,
                    tenant_config=True,
                )
                SaleRefundService.restoreStock(return_order, item, request)

            if shipping_refund > 0:
                commonQuery.updateRecordById(
                    Order,
                    sale_order["id"],
                    {"shipping": 0},
                    request=request,
                    tenant_config=True,
                )

            settlement = SaleRefundService.handleRefundSettlement(
                return_order,
                sale_order,
                customer,
                data,
                refund_total,
                settings,
                request,
            )
            updated_sale = SaleService.refreshOrder(sale_order["id"], request).data
            AccountingService.reflectEvent(
                "order_refunded",
                refund_total,
                name=f"Order refund {sale_order['code']}",
                transaction_type="adjustment",
                source_type="refund",
                source_id=return_order["id"],
                transaction_date=timezone.now(),
                description=data.get("note") or "Sale refunded",
                reference_number=sale_order["code"],
                request=request,
            )
            SaleService.reduceCashierStatsFromRefund(return_order["id"], request)
            SaleService.decreaseCustomerPurchasesFromRefund(return_order["id"], request)
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
        refunds = [SaleService.buildRefundDetail(refund["id"], request, refund=refund) for refund in refunds]
        return successResponse("Sale refunds retrieved successfully.", data=refunds)

    @staticmethod
    def buildRefundDetail(refund_id, request, refund=None):
        refund = refund or commonQuery.findOneRecord(
            OrdersRefund,
            refund_id,
            request=request,
            tenant_config=True,
        )
        if refund is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Refund not found.")

        sale_order = SaleService.buildSaleDetail(refund["sale_order_id"], request)
        payment_type = None
        if refund.get("payment_method"):
            payment_type = commonQuery.findOneRecord(
                PaymentType,
                {"identifier": refund["payment_method"], "status__in": [0, 1]},
                options={"attributes": ["id", "identifier", "label"]},
                request=request,
                tenant_config=True,
            )

        items = commonQuery.findAllRecords(
            OrdersProductsRefund,
            {"return_order_id": refund["id"]},
            {
                "attributes": [
                    "id",
                    "sale_order_id",
                    "return_order_id",
                    "sale_item_id",
                    "product_id",
                    "product__name",
                    "product__sku",
                    "product__barcode",
                    "unit_id",
                    "unit__name",
                    "quantity",
                    "unit_price",
                    "tax_amount",
                    "total",
                    "condition",
                    "description",
                    "created_at",
                ],
                "order": ["id"],
            },
            request=request,
            tenant_config=True,
        )

        subtotal = sum((money(item.get("total")) - money(item.get("tax_amount")) for item in items), Decimal("0"))
        total_quantity = sum((quantity(item.get("quantity")) for item in items), Decimal("0"))
        return {
            **refund,
            "sale_order": sale_order,
            "customer": sale_order.get("customer"),
            "cashier": sale_order.get("cashier"),
            "items": items,
            "refunded_products": items,
            "payment_type": payment_type,
            "payment_method_label": payment_type.get("label") if payment_type else refund.get("payment_method"),
            "subtotal": subtotal,
            "total_items": len(items),
            "total_quantity": total_quantity,
            "totals_summary": {
                "subtotal": subtotal,
                "tax_amount": money(refund.get("tax_amount")),
                "shipping": money(refund.get("shipping")),
                "total": money(refund.get("total")),
            },
        }

    @staticmethod
    def getRefundReceipt(refund_id, request):
        return successResponse(
            "Sale refund receipt retrieved successfully.",
            data=SaleService.buildRefundDetail(refund_id, request),
        )

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

    @staticmethod
    def resetSalesData(data, request):
        payload = data or {}
        reset_sales = payload.get("reset_sales", True)
        reset_stock_history = payload.get("reset_stock_history", True)
        reset_stock_quantity = payload.get("reset_stock_quantity", True)
        reset_customer_accounts = payload.get("reset_customer_accounts", True)
        reset_registers = payload.get("reset_registers", True)
        reset_transactions = payload.get("reset_transactions", True)

        summary = {}

        with transaction.atomic():
            if reset_sales:
                from apps.sales.models import (
                    Order,
                    OrderAddress,
                    OrderCount,
                    OrderInstalment,
                    OrderMeta,
                    OrderPayment,
                    OrdersProduct,
                    OrdersProductsRefund,
                    OrdersRefund,
                    OrderSetting,
                    OrderStorage,
                    OrderTax,
                )
                from apps.promotions.models import OrdersCoupon

                summary["orders_products_refund"] = commonQuery.branchScopedQueryset(OrdersProductsRefund, {}, request).delete()[0]
                summary["orders_refund"] = commonQuery.branchScopedQueryset(OrdersRefund, {}, request).delete()[0]
                summary["orders_product"] = commonQuery.branchScopedQueryset(OrdersProduct, {}, request).delete()[0]
                summary["order_payment"] = commonQuery.branchScopedQueryset(OrderPayment, {}, request).delete()[0]
                summary["order_instalment"] = commonQuery.branchScopedQueryset(OrderInstalment, {}, request).delete()[0]
                summary["order_address"] = commonQuery.branchScopedQueryset(OrderAddress, {}, request).delete()[0]
                summary["order_tax"] = commonQuery.branchScopedQueryset(OrderTax, {}, request).delete()[0]
                summary["order_meta"] = commonQuery.branchScopedQueryset(OrderMeta, {}, request).delete()[0]
                summary["order_setting"] = commonQuery.branchScopedQueryset(OrderSetting, {}, request).delete()[0]
                summary["order_storage"] = commonQuery.branchScopedQueryset(OrderStorage, {}, request).delete()[0]
                summary["order_count"] = commonQuery.branchScopedQueryset(OrderCount, {}, request).delete()[0]
                summary["orders_coupon"] = commonQuery.branchScopedQueryset(OrdersCoupon, {}, request).delete()[0]
                summary["orders"] = commonQuery.branchScopedQueryset(Order, {}, request).delete()[0]

            if reset_stock_history:
                from apps.catalog.models import ProductHistory, ProductHistoryCombined

                summary["product_history"] = commonQuery.branchScopedQueryset(ProductHistory, {}, request).delete()[0]
                summary["product_history_combined"] = commonQuery.branchScopedQueryset(ProductHistoryCombined, {}, request).delete()[0]

            if reset_stock_quantity:
                from apps.catalog.models import ProductUnitQuantity

                summary["products_stock_reset"] = commonQuery.branchScopedQueryset(ProductUnitQuantity, {}, request).update(quantity=0)

            if reset_customer_accounts:
                from apps.customers.models import CustomerAccountHistory, CustomerReward
                from apps.accounts.models import User

                summary["customer_account_history"] = commonQuery.branchScopedQueryset(CustomerAccountHistory, {}, request).delete()[0]
                summary["customer_rewards"] = commonQuery.branchScopedQueryset(CustomerReward, {}, request).delete()[0]

                customers_updated = commonQuery.branchScopedQueryset(User, {}, request).update(
                    owed_amount=Decimal("0"),
                    account_amount=Decimal("0"),
                    purchases_amount=Decimal("0"),
                    total_sales=Decimal("0"),
                    total_sales_count=0,
                )
                summary["customers_reset"] = customers_updated

            if reset_registers:
                from apps.registers.models import Register, RegistersHistory

                summary["registers_history"] = commonQuery.branchScopedQueryset(RegistersHistory, {}, request).delete()[0]
                summary["registers_reset"] = commonQuery.branchScopedQueryset(Register, {}, request).update(balance=Decimal("0"))

            if reset_transactions:
                from apps.accounting.models import TransactionBalanceDay, TransactionBalanceMonth, TransactionHistory
                from apps.reports.models import DashboardDay, DashboardMonth, DashboardWeek

                summary["transaction_history"] = commonQuery.branchScopedQueryset(TransactionHistory, {}, request).delete()[0]
                summary["transaction_balance_day"] = commonQuery.branchScopedQueryset(TransactionBalanceDay, {}, request).delete()[0]
                summary["transaction_balance_month"] = commonQuery.branchScopedQueryset(TransactionBalanceMonth, {}, request).delete()[0]
                summary["dashboard_day"] = commonQuery.branchScopedQueryset(DashboardDay, {}, request).delete()[0]
                summary["dashboard_week"] = commonQuery.branchScopedQueryset(DashboardWeek, {}, request).delete()[0]
                summary["dashboard_month"] = commonQuery.branchScopedQueryset(DashboardMonth, {}, request).delete()[0]

        return successResponse(
            "Sales records, product history, stock ledger, customer accounts, and register data have been successfully reset.",
            data={"summary": summary},
        )
