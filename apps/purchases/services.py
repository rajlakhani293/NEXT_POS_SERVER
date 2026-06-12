# type: ignore
from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.core.cache import cache

from apps.accounting.services import AccountingService
from apps.catalog.models import Product
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode, validateTenantRelationId, validateTenantRelationIds
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
        count = commonQuery.updateStatusById(Supplier, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Supplier not found.")
        return successResponse("Supplier status updated successfully.", data={"updated_count": count, "status": status})


class PurchaseOrderService:
    @staticmethod
    def orderDetail(order_id, request):
        order = commonQuery.findOneRecord(PurchaseOrder, order_id, request=request, tenant_config=True)
        if order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Purchase order not found.")
        supplier = commonQuery.findOneRecord(
            Supplier,
            order.get("supplier_id"),
            request=request,
            tenant_config=True,
        )
        order["items"] = commonQuery.findAllRecords(
            PurchaseItem,
            {"purchase_order_id": order_id},
            {
                "attributes": [
                    "id",
                    "product_id",
                    "product__name",
                    "ordered_quantity",
                    "received_quantity",
                    "cost_price",
                    "tax_amount",
                    "total",
                ],
                "order": ["id"],
            },
            request=request,
            tenant_config=True,
        )
        order["payments"] = commonQuery.findAllRecords(
            PurchasePayment,
            {"purchase_order_id": order_id},
            {
                "attributes": [
                    "id",
                    "payment_type",
                    "amount",
                    "paid_at",
                    "reference_number",
                    "note",
                ],
                "order": ["-paid_at", "-id"],
            },
            request=request,
            tenant_config=True,
        )
        order["supplier"] = supplier
        order["due_amount"] = max(money(order.get("total")) - money(order.get("paid_amount")), Decimal("0"))
        order["payment_status"] = (
            "paid"
            if money(order.get("paid_amount")) >= money(order.get("total"))
            else "partial"
            if money(order.get("paid_amount")) > 0
            else "unpaid"
        )
        return order

    @staticmethod
    def recalculateOrder(order_id, request):
        order = commonQuery.findOneRecord(PurchaseOrder, order_id, request=request, tenant_config=True)
        if order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Purchase order not found.")
        items = commonQuery.findAllRecords(
            PurchaseItem,
            {"purchase_order_id": order_id},
            {"attributes": ["id", "ordered_quantity", "received_quantity", "cost_price", "tax_amount", "total"]},
            request=request,
            tenant_config=True,
        )
        subtotal = sum(
            [qty(item.get("ordered_quantity")) * money(item.get("cost_price")) for item in items],
            Decimal("0"),
        )
        tax_amount = sum([money(item.get("tax_amount")) for item in items], Decimal("0"))
        total = subtotal - money(order.get("discount_amount")) + tax_amount + money(order.get("shipping_amount"))
        total_ordered = sum([qty(item.get("ordered_quantity")) for item in items], Decimal("0"))
        total_received = sum([qty(item.get("received_quantity")) for item in items], Decimal("0"))
        workflow_status = order.get("workflow_status") or "draft"
        if total_ordered > 0:
            workflow_status = (
                "received"
                if total_received >= total_ordered
                else "partial"
                if total_received > 0
                else order.get("workflow_status") or "ordered"
            )
        updated = commonQuery.updateRecordById(
            PurchaseOrder,
            order_id,
            {
                "subtotal": subtotal,
                "tax_amount": tax_amount,
                "total": total,
                "workflow_status": workflow_status,
            },
            request=request,
            tenant_config=True,
        )
        return updated

    @staticmethod
    def validateSupplier(supplier_id, request):
        supplier_id = validateTenantRelationId(
            Supplier,
            supplier_id,
            request=request,
            label="Supplier",
            required=True,
        )
        return {"id": supplier_id}

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
            validateTenantRelationIds(
                Product,
                [item.get("product_id") for item in items],
                request=request,
                label="Product",
            )
            for item in items:
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
    def getProducts(data, request):
        result = commonQuery.fetchPaginatedData(
            PurchaseItem,
            data,
            [["product__name", True, True], ["purchase_order__code", True, True]],
            {
                "attributes": [
                    "id",
                    "purchase_order_id",
                    "purchase_order__code",
                    "product_id",
                    "product__name",
                    "ordered_quantity",
                    "received_quantity",
                    "cost_price",
                    "tax_amount",
                    "total",
                    "created_at",
                    "status",
                ],
                "order": ["-id"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Procurement products retrieved successfully.", data=result)

    @staticmethod
    def getById(order_id, request):
        return successResponse("Purchase order retrieved successfully.", data=PurchaseOrderService.orderDetail(order_id, request))

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
                validateTenantRelationId(Product, item["product_id"], request=request, label="Product")
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
    def getOrderProducts(order_id, request):
        order = PurchaseOrderService.orderDetail(order_id, request)
        return successResponse("Procurement products retrieved successfully.", data=order.get("items") or [])

    @staticmethod
    def refresh(order_id, request):
        return successResponse("Procurement refreshed successfully.", data=PurchaseOrderService.orderDetail(order_id, request))

    @staticmethod
    def lowStockSuggestions(request):
        from apps.catalog.models import Product

        products = Product.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            track_stock=True,
            status__in=[0, 1],
            current_stock__lte=F("min_stock"),
        ).values(
            "id",
            "name",
            "sku",
            "current_stock",
            "min_stock",
            "purchase_price",
        ).order_by("current_stock", "name")[:100]
        return successResponse("Low stock suggestions retrieved successfully.", data=list(products))

    @staticmethod
    def storePreload(data, request):
        preload_key = uuid4().hex
        cache.set(
            f"procurement_preload:{request.user.company_id}:{request.user.branch_id}:{preload_key}",
            data or {},
            timeout=60 * 60 * 24,
        )
        return successResponse("Procurement preload saved successfully.", data={"uuid": preload_key, "payload": data or {}})

    @staticmethod
    def getPreload(preload_key, request):
        data = cache.get(
            f"procurement_preload:{request.user.company_id}:{request.user.branch_id}:{preload_key}"
        )
        if data is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement preload not found.")
        return successResponse("Procurement preload retrieved successfully.", data=data)

    @staticmethod
    def setAsPaid(order_id, request):
        order = PurchaseOrderService.orderDetail(order_id, request)
        due_amount = money(order.get("due_amount"))
        if due_amount <= 0:
            return successResponse("Procurement is already paid.", data=order)
        payment_data = {
            "amount": due_amount,
            "paid_at": timezone.now(),
            "payment_type": "account-payment",
            "reference_number": "",
            "note": "Set as paid from procurement action.",
        }
        PurchaseOrderService.pay(order_id, payment_data, request)
        return successResponse("Procurement marked as paid successfully.", data=PurchaseOrderService.orderDetail(order_id, request))

    @staticmethod
    def changePaymentStatus(order_id, data, request):
        order = PurchaseOrderService.orderDetail(order_id, request)
        payment_status = (data.get("payment_status") or "").lower()
        if payment_status not in ["paid", "partial", "unpaid"]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment status must be paid, partial or unpaid.")

        target_paid = Decimal("0")
        if payment_status == "paid":
            target_paid = money(order.get("total"))
        elif payment_status == "partial":
            target_paid = money(data.get("amount") or order.get("paid_amount") or 0)
            if target_paid <= 0 or target_paid >= money(order.get("total")):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Partial amount must be between 0 and total amount.")

        current_paid = money(order.get("paid_amount"))
        diff = target_paid - current_paid
        if diff == 0:
            return successResponse("Payment status updated successfully.", data=PurchaseOrderService.orderDetail(order_id, request))

        with transaction.atomic():
            commonQuery.updateRecordById(
                PurchaseOrder,
                order_id,
                {"paid_amount": target_paid},
                request=request,
                tenant_config=True,
            )
            Supplier.objects.filter(id=order["supplier_id"]).update(payable_amount=F("payable_amount") - diff)
        return successResponse("Payment status updated successfully.", data=PurchaseOrderService.orderDetail(order_id, request))

    @staticmethod
    def addProduct(order_id, data, request):
        order = commonQuery.findOneRecord(PurchaseOrder, order_id, request=request, tenant_config=True)
        if order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Purchase order not found.")
        items, _, _ = PurchaseOrderService.calculateItems([data])
        item = items[0]
        validateTenantRelationId(Product, item["product_id"], request=request, label="Product")
        created = commonQuery.createRecord(
            PurchaseItem,
            {**item, "purchase_order_id": order_id},
            request=request,
            tenant_config=True,
        )
        PurchaseOrderService.recalculateOrder(order_id, request)
        return successResponse("Procurement product added successfully.", data=created)

    @staticmethod
    def editProduct(order_id, purchase_item_id, data, request):
        order = commonQuery.findOneRecord(PurchaseOrder, order_id, request=request, tenant_config=True)
        if order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Purchase order not found.")
        item = commonQuery.findOneRecord(
            PurchaseItem,
            {"id": purchase_item_id, "purchase_order_id": order_id},
            request=request,
            tenant_config=True,
        )
        if item is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement product not found.")
        update_data = dict(data or {})
        if update_data.get("product_id"):
            validateTenantRelationId(Product, update_data["product_id"], request=request, label="Product")
        if update_data.get("ordered_quantity") is not None and qty(update_data.get("ordered_quantity")) < qty(item.get("received_quantity")):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Ordered quantity cannot be less than received quantity.")
        if "ordered_quantity" in update_data and "cost_price" in update_data:
            update_data["total"] = qty(update_data.get("ordered_quantity")) * money(update_data.get("cost_price")) + money(update_data.get("tax_amount"))
        updated = commonQuery.updateRecordById(
            PurchaseItem,
            purchase_item_id,
            update_data,
            request=request,
            tenant_config=True,
        )
        PurchaseOrderService.recalculateOrder(order_id, request)
        return successResponse("Procurement product updated successfully.", data=updated)

    @staticmethod
    def bulkUpdateProducts(order_id, data, request):
        items = data.get("items") or []
        if not items:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one product row is required.")
        with transaction.atomic():
            for item in items:
                purchase_item_id = item.get("purchase_item_id")
                if purchase_item_id:
                    PurchaseOrderService.editProduct(order_id, purchase_item_id, item, request)
                else:
                    PurchaseOrderService.addProduct(order_id, item, request)
        return successResponse("Procurement products updated successfully.", data=PurchaseOrderService.orderDetail(order_id, request))

    @staticmethod
    def deleteProduct(order_id, purchase_item_id, request):
        order = commonQuery.findOneRecord(PurchaseOrder, order_id, request=request, tenant_config=True)
        if order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Purchase order not found.")
        item = commonQuery.findOneRecord(
            PurchaseItem,
            {"id": purchase_item_id, "purchase_order_id": order_id},
            request=request,
            tenant_config=True,
        )
        if item is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement product not found.")
        if qty(item.get("received_quantity")) > 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Received procurement product cannot be deleted.")
        PurchaseItem.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            id=purchase_item_id,
            purchase_order_id=order_id,
        ).delete()
        PurchaseOrderService.recalculateOrder(order_id, request)
        return successResponse("Procurement product deleted successfully.")

    @staticmethod
    def searchProduct(data, request):
        from apps.catalog.models import Product

        search = (data or {}).get("search") or ""
        queryset = Product.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            status__in=[0, 1],
        )
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(sku__icontains=search)
                | Q(barcode__icontains=search)
            )
        rows = list(
            queryset.values("id", "name", "sku", "barcode", "purchase_price", "current_stock").order_by("name")[:25]
        )
        return successResponse("Products retrieved successfully.", data=rows)

    @staticmethod
    def searchProcurementProduct(data, request):
        search = (data or {}).get("search") or ""
        queryset = PurchaseItem.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            status__in=[0, 1],
        )
        if search:
            queryset = queryset.filter(
                Q(product__name__icontains=search)
                | Q(purchase_order__code__icontains=search)
            )
        rows = list(
            queryset.values(
                "id",
                "purchase_order_id",
                "purchase_order__code",
                "product_id",
                "product__name",
                "ordered_quantity",
                "received_quantity",
                "cost_price",
            ).order_by("-id")[:25]
        )
        return successResponse("Procurement products retrieved successfully.", data=rows)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(PurchaseOrder, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Purchase order not found.")
        return successResponse("Purchase orders deleted successfully.")
