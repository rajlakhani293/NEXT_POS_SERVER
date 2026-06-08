# type: ignore
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounting.services import AccountingService
from apps.catalog.models import Product
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode
from apps.common.responses import successResponse
from apps.inventory.models import StockLedger
from apps.notifications.services import NotificationService
from apps.payments.services import PaymentTypeService
from apps.purchases.models import PurchaseItem, PurchaseOrder, PurchasePayment, Supplier


def money(value):
    return Decimal(str(value or 0))


def qty(value):
    return Decimal(str(value or 0))


class SupplierService:
    @staticmethod
    def create(data, request):
        data["code"] = buildCode(Supplier, data.get("name"), data.get("code"), request)
        supplier = commonQuery.createRecord(Supplier, data, request=request, tenant_config=True)
        return successResponse("Supplier created successfully.", data=supplier)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            Supplier,
            data,
            [["name", True, True], ["code", True, True], ["phone", True, True], ["email", True, True]],
            {"attributes": ["id", "name", "code", "email", "phone", "contact_person", "tax_number", "payable_amount", "status"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Suppliers retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Supplier,
            {},
            {"attributes": ["id", "name", "code", "phone", "payable_amount"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def getById(supplier_id, request):
        supplier = commonQuery.findOneRecord(Supplier, supplier_id, request=request, tenant_config=True)
        if supplier is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Supplier not found.")
        return successResponse("Supplier retrieved successfully.", data=supplier)

    @staticmethod
    def update(supplier_id, data, request):
        if data.get("code"):
            data["code"] = buildCode(Supplier, data.get("name") or "Supplier", data.get("code"), request, exclude_id=supplier_id)
        updated = commonQuery.updateRecordById(Supplier, supplier_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Supplier not found.")
        return successResponse("Supplier updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Supplier, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Supplier not found.")
        return successResponse("Suppliers deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(Supplier, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Supplier not found.")
        return successResponse("Supplier status updated successfully.", data={"updated_count": count, "status": status})


class PurchaseOrderService:
    @staticmethod
    def validateSupplier(supplier_id, request):
        supplier = commonQuery.findOneRecord(Supplier, supplier_id, request=request, tenant_config=True)
        if supplier is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Supplier not found.")
        return supplier

    @staticmethod
    def calculateItems(items):
        subtotal = Decimal("0")
        tax_amount = Decimal("0")
        prepared = []
        for item in items or []:
            ordered_quantity = qty(item.get("ordered_quantity"))
            cost_price = money(item.get("cost_price"))
            if ordered_quantity <= 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Ordered quantity must be greater than 0.")
            product_id = item.get("product_id")
            line_tax = money(item.get("tax_amount"))
            line_total = (ordered_quantity * cost_price) + line_tax
            subtotal += ordered_quantity * cost_price
            tax_amount += line_tax
            prepared.append({**item, "product_id": product_id, "total": line_total})
        return prepared, subtotal, tax_amount

    @staticmethod
    def create(data, request):
        with transaction.atomic():
            supplier = PurchaseOrderService.validateSupplier(data.get("supplier_id"), request)
            items, subtotal, tax_amount = PurchaseOrderService.calculateItems(data.get("items") or [])
            total = subtotal - money(data.get("discount_amount")) + tax_amount + money(data.get("shipping_amount"))
            order = commonQuery.createRecord(
                PurchaseOrder,
                {
                    "supplier_id": supplier["id"],
                    "code": buildCode(PurchaseOrder, "Purchase Order", data.get("code"), request),
                    "order_date": data.get("order_date"),
                    "expected_date": data.get("expected_date") or None,
                    "workflow_status": data.get("workflow_status") or "draft",
                    "subtotal": subtotal,
                    "discount_amount": data.get("discount_amount") or 0,
                    "tax_amount": tax_amount,
                    "shipping_amount": data.get("shipping_amount") or 0,
                    "total": total,
                    "note": data.get("note") or "",
                },
                request=request,
                tenant_config=True,
            )
            created_items = []
            for item in items:
                product = commonQuery.findOneRecord(Product, item["product_id"], request=request, tenant_config=True)
                if product is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
                created_items.append(commonQuery.createRecord(PurchaseItem, {**item, "purchase_order_id": order["id"]}, request=request, tenant_config=True))
            Supplier.objects.filter(id=supplier["id"]).update(payable_amount=F("payable_amount") + total)
            order["items"] = created_items
            return successResponse("Purchase order created successfully.", data=order)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            PurchaseOrder,
            data,
            [["code", True, True], ["workflow_status", True, True], ["note", True, True]],
            {
                "attributes": [
                    "id",
                    "supplier_id",
                    "supplier__name",
                    "code",
                    "order_date",
                    "expected_date",
                    "workflow_status",
                    "subtotal",
                    "tax_amount",
                    "total",
                    "paid_amount",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Purchase orders retrieved successfully.", data=result)

    @staticmethod
    def getById(order_id, request):
        order = commonQuery.findOneRecord(PurchaseOrder, order_id, request=request, tenant_config=True)
        if order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Purchase order not found.")
        order["items"] = commonQuery.findAllRecords(
            PurchaseItem,
            {"purchase_order_id": order_id},
            {"attributes": ["id", "product_id", "product__name", "ordered_quantity", "received_quantity", "cost_price", "tax_amount", "total"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Purchase order retrieved successfully.", data=order)

    @staticmethod
    def update(order_id, data, request):
        if data.get("supplier_id"):
            PurchaseOrderService.validateSupplier(data.get("supplier_id"), request)
        updated = commonQuery.updateRecordById(PurchaseOrder, order_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Purchase order not found.")
        return successResponse("Purchase order updated successfully.", data=updated)

    @staticmethod
    def receive(order_id, data, request):
        with transaction.atomic():
            order = commonQuery.findOneRecord(PurchaseOrder, order_id, request=request, tenant_config=True)
            if order is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Purchase order not found.")
            total_ordered = Decimal("0")
            total_received = Decimal("0")
            received_now = Decimal("0")
            for item_data in data.get("items") or []:
                item = commonQuery.findOneRecord(PurchaseItem, item_data.get("purchase_item_id"), request=request, tenant_config=True)
                if item is None or item.get("purchase_order_id") != order_id:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Purchase item not found.")
                receive_qty = qty(item_data.get("received_quantity"))
                if receive_qty <= 0:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Received quantity must be greater than 0.")
                new_received = qty(item.get("received_quantity")) + receive_qty
                if new_received > qty(item.get("ordered_quantity")):
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Received quantity cannot exceed ordered quantity.")
                product = commonQuery.findOneRecord(Product, item["product_id"], request=request, tenant_config=True)
                Product.objects.filter(id=item["product_id"]).update(current_stock=F("current_stock") + receive_qty)
                PurchaseItem.objects.filter(id=item["id"]).update(received_quantity=new_received)
                commonQuery.createRecord(
                    StockLedger,
                    {
                        "product_id": item["product_id"],
                        "entry_type": "purchase",
                        "quantity": receive_qty,
                        "unit_cost": item.get("cost_price") or 0,
                        "balance_after": qty(product.get("current_stock")) + receive_qty,
                        "reference_type": "purchase_order",
                        "reference_id": order_id,
                        "note": data.get("note") or f"Purchase receive {order['code']}",
                    },
                    request=request,
                    tenant_config=True,
                )
                received_now += receive_qty
                try:
                    product_after = Product.objects.filter(id=item["product_id"]).values("name", "current_stock", "min_stock").first()
                    if product_after and product_after.get("current_stock") <= product_after.get("min_stock"):
                        NotificationService.push(
                            title="Low stock alert",
                            message=f"{product_after['name']} is at or below minimum stock.",
                            notification_type="warning",
                            source_type="inventory",
                            source_id=item["product_id"],
                            action_url=f"/inventory/products/{item['product_id']}",
                            request=request,
                        )
                except Exception:
                    pass
            for item in PurchaseItem.objects.filter(purchase_order_id=order_id):
                total_ordered += item.ordered_quantity
                total_received += item.received_quantity
            workflow_status = "received" if total_received >= total_ordered else "partial"
            updated = commonQuery.updateRecordById(PurchaseOrder, order_id, {"workflow_status": workflow_status}, request=request, tenant_config=True)
            return successResponse("Purchase received successfully.", data={**updated, "received_quantity": received_now})

    @staticmethod
    def pay(order_id, data, request):
        amount = money(data.get("amount"))
        if amount <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment amount must be greater than 0.")
        data["payment_type"] = PaymentTypeService.resolvePaymentType(data.get("payment_type"), request)
        with transaction.atomic():
            order = commonQuery.findOneRecord(PurchaseOrder, order_id, request=request, tenant_config=True)
            if order is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Purchase order not found.")
            payment = commonQuery.createRecord(
                PurchasePayment,
                {
                    "purchase_order_id": order_id,
                    "amount": amount,
                    "paid_at": data.get("paid_at") or timezone.now(),
                    "payment_type": data.get("payment_type") or "cash-payment",
                    "reference_number": data.get("reference_number") or "",
                    "note": data.get("note") or "",
                },
                request=request,
                tenant_config=True,
            )
            PurchaseOrder.objects.filter(id=order_id).update(paid_amount=F("paid_amount") + amount)
            Supplier.objects.filter(id=order["supplier_id"]).update(payable_amount=F("payable_amount") - amount)
            AccountingService.record(
                account_code=AccountingService.accountForPaymentType(data.get("payment_type")),
                name=f"Purchase payment {order['code']}",
                transaction_type="expense",
                action_type="debit",
                amount=amount,
                source_type="purchase",
                source_id=order_id,
                transaction_date=data.get("paid_at") or timezone.now(),
                description=data.get("note") or "Purchase payment",
                reference_number=data.get("reference_number") or "",
                request=request,
            )
            return successResponse("Purchase payment recorded successfully.", data=payment)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(PurchaseOrder, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Purchase order not found.")
        return successResponse("Purchase orders deleted successfully.")
