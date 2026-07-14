# type: ignore
from decimal import Decimal
from uuid import uuid4

from django.core.cache import cache
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.accounting.services import AccountingService
from apps.catalog.models import Product, ProductHistory, ProductUnitQuantity, TaxGroup, Unit
from apps.catalog.services import ProductStockService
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import (
    decimalValue as money,
    decimalValue as qty,
    validateTenantRelationId,
    validateUniqueFields,
)
from apps.common.responses import successResponse
from apps.settings.services import NotificationService
from apps.purchases.models import ProcurementsProduct, Procurement, Provider


class SupplierService:
    @staticmethod
    def displayName(row):
        return " ".join([part for part in [row.get("first_name"), row.get("last_name")] if part]).strip()

    @staticmethod
    def create(data, request):
        if data.get("email"):
            validateUniqueFields(
                Provider,
                {"email": data.get("email")},
                request=request,
                scope="branch",
                status_in=(0, 1),
                case_insensitive=["email"],
                messages={"email": "Provider email already exists."},
            )
        data["uuid"] = data.get("uuid") or uuid4().hex
        provider = commonQuery.createRecord(Provider, data, request=request, tenant_config=True)
        provider["name"] = SupplierService.displayName(provider)
        return successResponse("The provider has been created.", data=provider)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            Provider,
            data,
            [["first_name", True, True], ["last_name", True, True], ["phone", True, True], ["email", True, True]],
            {
                "attributes": [
                    "id",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "address_1",
                    "address_2",
                    "description",
                    "amount_due",
                    "amount_paid",
                    "uuid",
                    "status",
                    "user__username",
                    "created_at",
                ]
            },
            request=request,
            tenant_config=True,
        )
        for item in result["items"]:
            item["name"] = SupplierService.displayName(item)
            item["payable_amount"] = item.get("amount_due")
            item["user_username"] = item.pop("user__username", None)
        return successResponse("Suppliers retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        rows = commonQuery.findAllRecords(
            Provider,
            {},
            {"attributes": ["id", "first_name", "last_name", "phone", "amount_due"], "order": ["first_name"]},
            request=request,
            tenant_config=True,
        )
        for row in rows:
            row["name"] = SupplierService.displayName(row)
            row["payable_amount"] = row.get("amount_due")
        return successResponse("Dropdown list retrieved successfully.", data=rows)

    @staticmethod
    def getById(supplier_id, request):
        provider = commonQuery.findOneRecord(Provider, supplier_id, request=request, tenant_config=True)
        if provider is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Provider not found.")
        provider["name"] = SupplierService.displayName(provider)
        provider["payable_amount"] = provider.get("amount_due")
        return successResponse("Provider retrieved successfully.", data=provider)

    @staticmethod
    def computeSummary(provider_id, request):
        provider = commonQuery.findOneRecord(Provider, provider_id, request=request, tenant_config=True)
        if provider is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Provider not found.")
        rows = commonQuery.branchScopedQueryset(Procurement, {"provider_id": provider_id}, request).exclude(status=2)
        amount_paid = Decimal("0")
        amount_due = Decimal("0")
        for row in rows.values("value", "payment_status"):
            value = money(row.get("value"))
            if row.get("payment_status") == "paid":
                amount_paid += value
            else:
                amount_due += value
        updated = commonQuery.updateRecordById(
            Provider,
            provider_id,
            {"amount_paid": amount_paid, "amount_due": amount_due},
            request=request,
            tenant_config=True,
        )
        if updated:
            updated["name"] = SupplierService.displayName(updated)
            updated["payable_amount"] = updated.get("amount_due")
        return successResponse("Provider summary computed successfully.", data=updated)

    @staticmethod
    def update(supplier_id, data, request):
        if data.get("email"):
            validateUniqueFields(
                Provider,
                {"email": data.get("email")},
                request=request,
                scope="branch",
                exclude_id=supplier_id,
                status_in=(0, 1),
                case_insensitive=["email"],
                messages={"email": "Provider email already exists."},
            )
        updated = commonQuery.updateRecordById(Provider, supplier_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Provider not found.")
        updated["name"] = SupplierService.displayName(updated)
        updated["payable_amount"] = updated.get("amount_due")
        return successResponse("The provider has been updated.", data=updated)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Provider, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Provider not found.")
        return successResponse("The provider has been deleted.")

    @staticmethod
    def updateStatus(data, request):
        count = commonQuery.updateStatusById(
            Provider,
            data.get("ids"),
            data.get("status"),
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Provider not found.")
        return successResponse("Provider status updated successfully.", data={"updated_count": count, "status": data.get("status")})

    @staticmethod
    def products(provider_id, data, request):
        provider = commonQuery.findOneRecord(Provider, provider_id, request=request, tenant_config=True)
        if provider is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Provider not found.")
        result = commonQuery.fetchPaginatedData(
            ProcurementsProduct,
            {
                **(data or {}),
                "filter": {
                    **((data or {}).get("filter") or {}),
                    "procurement__provider_id": provider_id,
                },
            },
            [["name", True, True], ["product__name", True, True], ["procurement__name", True, True], ["barcode", True, True]],
            {
                "attributes": [
                    "id",
                    "procurement_id",
                    "procurement__name",
                    "product_id",
                    "product__name",
                    "name",
                    "purchase_price",
                    "quantity",
                    "available_quantity",
                    "tax_group_id",
                    "tax_group__name",
                    "barcode",
                    "expiration_date",
                    "tax_type",
                    "tax_value",
                    "total_purchase_price",
                    "unit_id",
                    "unit__name",
                    "created_at",
                    "status",
                ],
                "order": ["-id"],
            },
            request=request,
            tenant_config=True,
        )
        for item in result["items"]:
            item["procurement_name"] = item.pop("procurement__name", None)
            item["product_name"] = item.pop("product__name", None)
            item["unit_name"] = item.pop("unit__name", None)
            item["tax_group_name"] = item.pop("tax_group__name", None)
            item["ordered_quantity"] = item.get("quantity")
            item["received_quantity"] = qty(item.get("quantity")) - qty(item.get("available_quantity"))
            item["cost_price"] = item.get("purchase_price")
            item["total"] = item.get("total_purchase_price")
        return successResponse("Provider products retrieved successfully.", data=result)


class PurchaseOrderService:
    PAYMENT_PAID = "paid"
    PAYMENT_UNPAID = "unpaid"
    DELIVERY_DRAFT = "draft"
    DELIVERY_PENDING = "pending"
    DELIVERY_DELIVERED = "delivered"
    DELIVERY_STOCKED = "stocked"

    @staticmethod
    def requestFromJob(job):
        from apps.common.helpers import requestFromJobUser

        return requestFromJobUser(job)

    @staticmethod
    def procurementName():
        last_id = commonQuery.scopedQueryset(Procurement, {}, tenant_config={}).order_by("-id").values_list("id", flat=True).first() or 0
        return str(last_id + 1).zfill(5)

    @staticmethod
    def validateSupplier(provider_id, request):
        provider_id = validateTenantRelationId(
            Provider,
            provider_id,
            request=request,
            label="Provider",
            required=True,
        )
        return {"id": provider_id}

    @staticmethod
    def sourceOrderPayload(data):
        data = dict(data or {})
        if "general" not in data:
            return data
        general = dict(data.get("general") or {})
        missing = [
            field
            for field in ["provider_id", "payment_status", "delivery_status"]
            if general.get(field) in [None, ""]
        ]
        if missing:
            raise api_error(
                422,
                ErrorCodes.VALIDATION_ERROR,
                f"Missing required procurement general field(s): {', '.join(missing)}.",
            )
        normalized = {
            **general,
            "name": data.get("name") or general.get("name"),
            "products": data.get("products") or data.get("items") or general.get("products") or [],
        }
        for key, value in data.items():
            if key not in {"general", "name", "products", "items"}:
                normalized[key] = value
        return normalized

    @staticmethod
    def sourceItemsPayload(data):
        data = dict(data or {})
        return data.get("items") or data.get("products") or []

    @staticmethod
    def resolveProductUnitQuantity(product_id, unit_id, request, required=False):
        validateTenantRelationId(Product, product_id, request=request, label="Product")
        validateTenantRelationId(Unit, unit_id, request=request, label="Unit", required=True)
        unit_quantity = commonQuery.findOneRecord(
            ProductUnitQuantity,
            {"product_id": product_id, "unit_id": unit_id},
            request=request,
            tenant_config=True,
        )
        if unit_quantity is None and required:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product unit quantity not found.")
        return unit_quantity

    @staticmethod
    def normalizeProductItem(item, request):
        product = commonQuery.findOneRecord(Product, item.get("product_id"), request=request, tenant_config=True)
        if product is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        if product.get("stock_management") == "disabled":
            raise api_error(400, ErrorCodes.BAD_REQUEST, f"Unable to procure {product.get('name')} because stock management is disabled.")
        if product.get("type") == "grouped":
            raise api_error(400, ErrorCodes.BAD_REQUEST, f"Unable to procure {product.get('name')} because it is a grouped product.")
        validateTenantRelationId(Unit, item.get("unit_id"), request=request, label="Unit", required=True)
        if item.get("convert_unit_id"):
            item["convert_unit_id"] = validateTenantRelationId(Unit, item["convert_unit_id"], request=request, label="Convert unit", required=False)
        if item.get("tax_group_id"):
            item["tax_group_id"] = validateTenantRelationId(TaxGroup, item["tax_group_id"], request=request, label="Tax group", required=False)

        quantity = qty(item.get("quantity"))
        if quantity <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Quantity must be greater than 0.")
        purchase_price = money(item.get("purchase_price"))
        tax_value = money(item.get("tax_value"))
        total_purchase_price = item.get("total_purchase_price")
        if total_purchase_price is None:
            total_purchase_price = (purchase_price * quantity) + tax_value
        return {
            "name": item.get("name") or product.get("name"),
            "product_id": product["id"],
            "gross_purchase_price": item.get("gross_purchase_price") or purchase_price,
            "net_purchase_price": item.get("net_purchase_price") or purchase_price,
            "purchase_price": purchase_price,
            "quantity": quantity,
            "available_quantity": item.get("available_quantity") if item.get("available_quantity") is not None else quantity,
            "tax_group_id": item.get("tax_group_id"),
            "barcode": item.get("barcode"),
            "expiration_date": item.get("expiration_date") or None,
            "tax_type": item.get("tax_type") or "exclusive",
            "tax_value": tax_value,
            "total_purchase_price": total_purchase_price,
            "unit_id": item.get("unit_id"),
            "convert_unit_id": item.get("convert_unit_id"),
            "uuid": item.get("uuid") or uuid4().hex,
        }

    @staticmethod
    def createOrUpdateProductRow(procurement_id, item, request):
        purchase_item_id = item.pop("purchase_item_id", None) or item.pop("id", None)
        if purchase_item_id:
            existing = commonQuery.findOneRecord(
                ProcurementsProduct,
                {"id": purchase_item_id, "procurement_id": procurement_id},
                request=request,
                tenant_config=True,
            )
            if existing is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement product not found.")
            updated = commonQuery.updateRecordById(
                ProcurementsProduct,
                purchase_item_id,
                item,
                request=request,
                tenant_config=True,
            )
            PurchaseOrderService.ensureProcurementProductBarcode(purchase_item_id, request)
            return updated
        created = commonQuery.createRecord(
            ProcurementsProduct,
            {**item, "procurement_id": procurement_id},
            request=request,
            tenant_config=True,
        )
        return PurchaseOrderService.ensureProcurementProductBarcode(created["id"], request)

    @staticmethod
    def ensureProcurementProductBarcode(purchase_item_id, request):
        item = commonQuery.findOneRecord(
            ProcurementsProduct,
            purchase_item_id,
            request=request,
            tenant_config=True,
        )
        if item is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement product not found.")
        product = commonQuery.findOneRecord(Product, item.get("product_id"), request=request, tenant_config=True) or {}
        generated = f"{str(product.get('barcode') or '').zfill(5)}-{str(item.get('unit_id') or '').zfill(3)}-{str(item['id']).zfill(3)}"
        if item.get("barcode") != generated:
            item = commonQuery.updateRecordById(
                ProcurementsProduct,
                item["id"],
                {"barcode": generated},
                request=request,
                tenant_config=True,
            )
        return item

    @staticmethod
    def calculateProducts(products, request):
        prepared = []
        value = Decimal("0")
        tax_value = Decimal("0")
        for item in products or []:
            row = PurchaseOrderService.normalizeProductItem(item, request)
            value += money(row["total_purchase_price"])
            tax_value += money(row["tax_value"])
            prepared.append(row)
        return prepared, value, tax_value

    @staticmethod
    def orderDetail(order_id, request):
        order = commonQuery.findOneRecord(Procurement, order_id, request=request, tenant_config=True)
        if order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement not found.")
        provider = commonQuery.findOneRecord(Provider, order.get("provider_id"), request=request, tenant_config=True)
        products = commonQuery.findAllRecords(
            ProcurementsProduct,
            {"procurement_id": order_id},
            {
                "attributes": [
                    "id",
                    "procurement_id",
                    "product_id",
                    "product__name",
                    "name",
                    "gross_purchase_price",
                    "net_purchase_price",
                    "purchase_price",
                    "quantity",
                    "available_quantity",
                    "tax_group_id",
                    "barcode",
                    "expiration_date",
                    "tax_type",
                    "tax_value",
                    "total_purchase_price",
                    "unit_id",
                    "unit__name",
                    "convert_unit_id",
                    "uuid",
                    "status",
                ],
                "order": ["id"],
            },
            request=request,
            tenant_config=True,
        )
        if provider:
            provider["name"] = SupplierService.displayName(provider)
        for product in products:
            product["ordered_quantity"] = qty(product.get("quantity"))
            product["received_quantity"] = qty(product.get("quantity")) - qty(product.get("available_quantity"))
            product["cost_price"] = product.get("purchase_price")
            product["tax_amount"] = product.get("tax_value")
            product["total"] = product.get("total_purchase_price")
        is_paid = order.get("payment_status") == "paid"
        total_value = money(order.get("value"))
        order["provider"] = provider
        order["Provider"] = provider
        order["supplier"] = provider
        order["products"] = products
        order["items"] = products
        order["due_amount"] = Decimal("0") if is_paid else total_value
        order["code"] = order.get("name")
        order["order_date"] = order.get("invoice_date")
        order["expected_date"] = order.get("delivery_time")
        order["total"] = order.get("value")
        order["paid_amount"] = total_value if is_paid else Decimal("0")
        order["workflow_status"] = order.get("delivery_status")
        return order

    @staticmethod
    def recalculateOrder(order_id, request):
        products = commonQuery.findAllRecords(
            ProcurementsProduct,
            {"procurement_id": order_id},
            {"attributes": ["id", "quantity", "available_quantity", "purchase_price", "tax_value", "total_purchase_price"]},
            request=request,
            tenant_config=True,
        )
        value = sum((money(item.get("total_purchase_price")) for item in products), Decimal("0"))
        tax_value = sum((money(item.get("tax_value")) for item in products), Decimal("0"))
        total_items = sum((qty(item.get("quantity")) for item in products), Decimal("0"))
        delivered = bool(products) and all(qty(item.get("available_quantity")) <= 0 for item in products)
        return commonQuery.updateRecordById(
            Procurement,
            order_id,
            {
                "value": value,
                "cost": value - tax_value,
                "tax_value": tax_value,
                "total_items": int(total_items),
                "delivery_status": "stocked" if delivered else "pending",
            },
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def create(data, request):
        data = PurchaseOrderService.sourceOrderPayload(data)
        with transaction.atomic():
            provider = PurchaseOrderService.validateSupplier(data.get("provider_id"), request)
            products, value, tax_value = PurchaseOrderService.calculateProducts(data.get("products") or data.get("items") or [], request)
            procurement = commonQuery.createRecord(
                Procurement,
                {
                    "provider_id": provider["id"],
                    "name": data.get("name") or PurchaseOrderService.procurementName(),
                    "value": value,
                    "cost": value - tax_value,
                    "tax_value": tax_value,
                    "invoice_reference": data.get("invoice_reference"),
                    "automatic_approval": data.get("automatic_approval") or False,
                    "delivery_time": data.get("delivery_time") or None,
                    "invoice_date": data.get("invoice_date") or None,
                    "payment_status": data.get("payment_status") or PurchaseOrderService.PAYMENT_UNPAID,
                    "delivery_status": data.get("delivery_status") or PurchaseOrderService.DELIVERY_PENDING,
                    "total_items": int(sum((qty(item.get("quantity")) for item in products), Decimal("0"))),
                    "description": data.get("description"),
                    "uuid": data.get("uuid") or uuid4().hex,
                },
                request=request,
                tenant_config=True,
            )
            created_products = [
                PurchaseOrderService.createOrUpdateProductRow(procurement["id"], item, request)
                for item in products
            ]
            if procurement.get("delivery_status") == PurchaseOrderService.DELIVERY_DELIVERED:
                receive_items = [
                    {
                        "purchase_item_id": item["id"],
                        "received_quantity": item.get("available_quantity") or item.get("quantity") or 0,
                    }
                    for item in created_products
                    if qty(item.get("available_quantity") or item.get("quantity")) > 0
                ]
                if receive_items:
                    procurement = PurchaseOrderService.receive(
                        procurement["id"],
                        {"items": receive_items, "note": f"Procurement receive {procurement['name']}"},
                        request,
                    ).data
                    procurement["products"] = created_products
                    procurement["items"] = created_products
            commonQuery.branchScopedQueryset(Provider, {"id": provider["id"]}, request).update(
                amount_due=F("amount_due") + float(value)
            )
            AccountingService.reflectEvent(
                "procurement_unpaid",
                value,
                name=f"Procurement {procurement['name']}",
                transaction_type="expense",
                source_type="purchase",
                source_id=procurement["id"],
                transaction_date=procurement.get("invoice_date") or timezone.now(),
                description=procurement.get("description") or "Procurement created",
                reference_number=procurement.get("invoice_reference") or procurement["name"],
                request=request,
            )
            SupplierService.computeSummary(provider["id"], request)
            procurement["products"] = created_products
            procurement["items"] = created_products
            return successResponse("Procurement created successfully.", data=procurement)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            Procurement,
            data,
            [["name", True, True], ["invoice_reference", True, True], ["payment_status", True, True], ["delivery_status", True, True]],
            {
                "attributes": [
                    "id",
                    "name",
                    "provider_id",
                    "provider__first_name",
                    "provider__last_name",
                    "value",
                    "cost",
                    "tax_value",
                    "invoice_reference",
                    "automatic_approval",
                    "delivery_time",
                    "invoice_date",
                    "payment_status",
                    "delivery_status",
                    "total_items",
                    "description",
                    "uuid",
                    "status",
                    "user__username",
                    "created_at",
                ]
            },
            request=request,
            tenant_config=True,
        )
        for item in result["items"]:
            item["provider_name"] = SupplierService.displayName({"first_name": item.pop("provider__first_name", None), "last_name": item.pop("provider__last_name", None)})
            item["supplier_id"] = item.get("provider_id")
            item["supplier_name"] = item["provider_name"]
            item["code"] = item.get("name")
            item["total"] = item.get("value")
            item["workflow_status"] = item.get("delivery_status")
            item["user_username"] = item.pop("user__username", None)
        return successResponse("Procurements retrieved successfully.", data=result)

    @staticmethod
    def getProducts(data, request):
        result = commonQuery.fetchPaginatedData(
            ProcurementsProduct,
            data,
            [["name", True, True], ["product__name", True, True], ["procurement__name", True, True], ["barcode", True, True]],
            {
                "attributes": [
                    "id",
                    "procurement_id",
                    "procurement__name",
                    "product_id",
                    "product__name",
                    "name",
                    "purchase_price",
                    "quantity",
                    "available_quantity",
                    "tax_group_id",
                    "barcode",
                    "expiration_date",
                    "tax_value",
                    "total_purchase_price",
                    "unit_id",
                    "unit__name",
                    "user__username",
                    "created_at",
                    "status",
                ],
                "order": ["-id"],
            },
            request=request,
            tenant_config=True,
        )
        for item in result["items"]:
            item["purchase_order_id"] = item.get("procurement_id")
            item["purchase_order__code"] = item.pop("procurement__name", None)
            item["procurement_name"] = item.get("purchase_order__code")
            item["unit_name"] = item.pop("unit__name", None)
            item["user_username"] = item.pop("user__username", None)
            item["ordered_quantity"] = item.get("quantity")
            item["received_quantity"] = qty(item.get("quantity")) - qty(item.get("available_quantity"))
            item["cost_price"] = item.get("purchase_price")
            item["total"] = item.get("total_purchase_price")
        return successResponse("Procurement products retrieved successfully.", data=result)

    @staticmethod
    def getById(order_id, request):
        return successResponse("Procurement retrieved successfully.", data=PurchaseOrderService.orderDetail(order_id, request))

    @staticmethod
    def update(order_id, data, request):
        data = PurchaseOrderService.sourceOrderPayload(data)
        procurement = commonQuery.findOneRecord(Procurement, order_id, request=request, tenant_config=True)
        if procurement is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement not found.")
        if procurement.get("delivery_status") == PurchaseOrderService.DELIVERY_STOCKED:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unable to edit a procurement that has already been stocked. Please use stock adjustment.")
        if data.get("provider_id"):
            PurchaseOrderService.validateSupplier(data.get("provider_id"), request)
        products_payload = data.pop("products", None)
        data.pop("items", None)
        updated = commonQuery.updateRecordById(Procurement, order_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement not found.")
        if products_payload is not None:
            for item in products_payload:
                normalized = PurchaseOrderService.normalizeProductItem(item, request)
                if item.get("id") or item.get("purchase_item_id"):
                    normalized["purchase_item_id"] = item.get("purchase_item_id") or item.get("id")
                PurchaseOrderService.createOrUpdateProductRow(order_id, normalized, request)
            updated = PurchaseOrderService.recalculateOrder(order_id, request)
        if procurement.get("provider_id"):
            SupplierService.computeSummary(procurement["provider_id"], request)
        if updated.get("provider_id") and updated.get("provider_id") != procurement.get("provider_id"):
            SupplierService.computeSummary(updated["provider_id"], request)
        return successResponse("Procurement updated successfully.", data=updated)

    @staticmethod
    def receive(order_id, data, request):
        with transaction.atomic():
            procurement = commonQuery.findOneRecord(Procurement, order_id, request=request, tenant_config=True)
            if procurement is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement not found.")
            received_now = Decimal("0")
            for item_data in data.get("items") or []:
                item = commonQuery.findOneRecord(ProcurementsProduct, item_data.get("purchase_item_id"), request=request, tenant_config=True)
                if item is None or item.get("procurement_id") != order_id:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement product not found.")
                receive_qty = qty(item_data.get("received_quantity"))
                if receive_qty <= 0:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Received quantity must be greater than 0.")
                if receive_qty > qty(item.get("available_quantity")):
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Received quantity cannot exceed available procurement quantity.")
                unit_quantity = PurchaseOrderService.resolveProductUnitQuantity(item["product_id"], item["unit_id"], request, required=True)
                new_available = qty(item.get("available_quantity")) - receive_qty
                commonQuery.branchScopedQueryset(ProcurementsProduct, {"id": item["id"]}, request).update(
                    available_quantity=float(new_available)
                )
                ProductStockService.recordStockHistory(
                    ProductHistory.ACTION_STOCKED,
                    {
                        "product_id": item["product_id"],
                        "procurement_id": order_id,
                        "procurement_product_id": item["id"],
                        "quantity": receive_qty,
                        "unit_id": item["unit_id"],
                        "unit_price": item.get("purchase_price") or 0,
                        "cogs": item.get("purchase_price") or 0,
                        "description": data.get("note") or f"Procurement receive {procurement['name']}",
                    },
                    request,
                )

                # Check if unit conversion is defined
                convert_unit_id = item.get("convert_unit_id")
                if convert_unit_id:
                    from_unit = commonQuery.findOneRecord(Unit, item["unit_id"], request=request, tenant_config=True)
                    to_unit = commonQuery.findOneRecord(Unit, convert_unit_id, request=request, tenant_config=True)
                    
                    if not from_unit or not to_unit:
                        raise api_error(404, ErrorCodes.NOT_FOUND, "Source or destination unit not found for conversion.")
                    
                    if from_unit.get("group_id") != to_unit.get("group_id"):
                        raise api_error(400, ErrorCodes.BAD_REQUEST, "Source and destination units do not belong to the same unit group.")
                    
                    # Ensure the destination ProductUnitQuantity exists in catalog
                    dest_uq = commonQuery.branchScopedQueryset(
                        ProductUnitQuantity,
                        {"product_id": item["product_id"], "unit_id": convert_unit_id, "status__in": [0, 1]},
                        request,
                    ).first()
                    
                    if not dest_uq:
                        commonQuery.createRecord(
                            ProductUnitQuantity,
                            {
                                "product_id": item["product_id"],
                                "unit_id": convert_unit_id,
                                "quantity": 0.0,
                                "visible": False,
                            },
                            request=request,
                            tenant_config=True
                        )
                    
                    # Conversion calculations
                    from_val = Decimal(str(from_unit.get("value") or 1.0))
                    to_val = Decimal(str(to_unit.get("value") or 1.0))
                    converted_qty = (from_val * receive_qty) / to_val
                    
                    source_price = Decimal(str(item.get("purchase_price") or 0.0))
                    converted_price = (source_price * to_val) / from_val
                    
                    # 1. Convert OUT from source unit
                    ProductStockService.recordStockHistory(
                        ProductHistory.ACTION_CONVERT_OUT,
                        {
                            "product_id": item["product_id"],
                            "procurement_id": order_id,
                            "procurement_product_id": item["id"],
                            "quantity": receive_qty,
                            "unit_id": item["unit_id"],
                            "unit_price": float(source_price),
                            "total_price": float(source_price * receive_qty),
                            "description": f"Unit conversion out during receive of procurement #{order_id}",
                        },
                        request,
                    )
                    
                    # 2. Convert IN to destination unit
                    ProductStockService.recordStockHistory(
                        ProductHistory.ACTION_CONVERT_IN,
                        {
                            "product_id": item["product_id"],
                            "procurement_id": order_id,
                            "procurement_product_id": item["id"],
                            "quantity": float(converted_qty),
                            "unit_id": convert_unit_id,
                            "unit_price": float(converted_price),
                            "total_price": float(source_price * receive_qty),
                            "description": f"Unit conversion in during receive of procurement #{order_id}",
                        },
                        request,
                    )

                latest_unit_quantity = commonQuery.findOneRecord(ProductUnitQuantity, unit_quantity["id"], request=request, tenant_config=True)
                if latest_unit_quantity and latest_unit_quantity.get("stock_alert_enabled") and qty(latest_unit_quantity.get("quantity")) < qty(latest_unit_quantity.get("low_quantity")):
                    NotificationService.push(
                        title="Low stock alert",
                        message=f"{item['name']} is at or below minimum stock.",
                        notification_type="warning",
                        source_type="inventory",
                        source_id=item["product_id"],
                        action_url=f"/inventory/products/{item['product_id']}",
                        request=request,
                    )
                received_now += receive_qty
            has_available = commonQuery.branchScopedQueryset(
                ProcurementsProduct,
                {"procurement_id": order_id, "available_quantity__gt": 0, "status__in": [0, 1]},
                request,
            ).exists()
            updated = commonQuery.updateRecordById(
                Procurement,
                order_id,
                {"delivery_status": "pending" if has_available else "stocked"},
                request=request,
                tenant_config=True,
            )
            return successResponse("Procurement received successfully.", data={**updated, "received_quantity": received_now})

    @staticmethod
    def stockAwaitingProcurements(request):
        due_procurements = list(
            commonQuery.branchScopedQueryset(
                Procurement,
                {
                    "status__in": [0, 1],
                    "automatic_approval": True,
                    "delivery_status": PurchaseOrderService.DELIVERY_PENDING,
                    "delivery_time__lte": timezone.now(),
                },
                request,
            ).values("id")
        )
        stocked_count = 0
        for procurement in due_procurements:
            items = commonQuery.findAllRecords(
                ProcurementsProduct,
                {"procurement_id": procurement["id"]},
                {"attributes": ["id", "available_quantity"]},
                request=request,
                tenant_config=True,
            )
            receive_items = [
                {"purchase_item_id": item["id"], "received_quantity": item.get("available_quantity") or 0}
                for item in items
                if qty(item.get("available_quantity")) > 0
            ]
            if not receive_items:
                continue
            PurchaseOrderService.receive(
                procurement["id"],
                {"items": receive_items, "note": "Auto-stocked approved procurement."},
                request,
            )
            stocked_count += 1
        if stocked_count:
            NotificationService.push(
                title="Procurement Automatically Stocked",
                message=f"{stocked_count} procurement(s) have recently been automatically stocked.",
                notification_type="info",
                source_type="purchase",
                source_id=None,
                action_url="/purchases",
                request=request,
            )
        return successResponse("Awaiting procurements stocked successfully.", data={"stocked_count": stocked_count})

    @staticmethod
    def getOrderProducts(order_id, request):
        procurement = PurchaseOrderService.orderDetail(order_id, request)
        return successResponse("Procurement products retrieved successfully.", data=procurement.get("products") or [])

    @staticmethod
    def refresh(order_id, request):
        PurchaseOrderService.recalculateOrder(order_id, request)
        return successResponse("Procurement refreshed successfully.", data=PurchaseOrderService.orderDetail(order_id, request))

    @staticmethod
    def enqueueRefresh(order_id, request):
        from apps.settings.services import JobQueueService

        job = JobQueueService.enqueue("refresh_procurement", {"procurement_id": order_id}, request=request)
        return successResponse("Procurement refresh queued successfully.", data={"job_id": job.id})

    @staticmethod
    def enqueueStockAwaiting(data, request):
        from apps.settings.services import JobQueueService

        job = JobQueueService.enqueue("stock_awaiting_procurements", data or {}, request=request)
        return successResponse("Stock awaiting procurements queued successfully.", data={"job_id": job.id})

    @staticmethod
    def lowStockSuggestions(request):
        rows = commonQuery.branchScopedQueryset(
            ProductUnitQuantity,
            {"status__in": [0, 1], "stock_alert_enabled": True, "quantity__lt": F("low_quantity")},
            request,
        ).filter(
            product__stock_management="enabled",
            product__type__in=["dematerialized", "materialized"],
        ).values(
            "id",
            "product_id",
            "product__name",
            "product__sku",
            "product__barcode",
            "product__tax_group_id",
            "product__tax_type",
            "quantity",
            "low_quantity",
            "cogs",
            "unit_id",
            "unit__name",
        ).order_by("quantity", "product__name")[:50]
        products = []
        for row in rows:
            recent = commonQuery.branchScopedQueryset(
                ProcurementsProduct,
                {
                    "product_id": row["product_id"],
                    "unit_id": row["unit_id"],
                    "procurement__delivery_status": PurchaseOrderService.DELIVERY_STOCKED,
                    "status__in": [0, 1],
                },
                request,
            ).order_by("-created_at", "-id").values("quantity", "unit_id", "convert_unit_id", "purchase_price", "convert_unit__name").first()
            row["product_name"] = row.pop("product__name", None)
            row["sku"] = row.pop("product__sku", None)
            row["barcode"] = row.pop("product__barcode", None)
            row["tax_group_id"] = row.pop("product__tax_group_id", None)
            row["tax_type"] = row.pop("product__tax_type", None)
            row["unit_name"] = row.pop("unit__name", None)
            if recent:
                row["recent_procured_quantity"] = recent.get("quantity")
                row["recent_procured_unit_id"] = recent.get("unit_id")
                row["recent_procured_convert_unit_id"] = recent.get("convert_unit_id")
                row["recent_procured_convert_unit_label"] = recent.get("convert_unit__name")
                row["recent_procured_purchase_price"] = recent.get("purchase_price")
            else:
                row["recent_procured_quantity"] = row.get("low_quantity")
                row["recent_procured_unit_id"] = row.get("unit_id")
                row["recent_procured_convert_unit_id"] = None
                row["recent_procured_convert_unit_label"] = None
                row["recent_procured_purchase_price"] = row.get("cogs") or 0
            products.append(row)
        return successResponse("Low stock suggestions retrieved successfully.", data=products)

    @staticmethod
    def storePreload(data, request):
        items = (data or {}).get("products") or (data or {}).get("items") or []
        if not items:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unable to save the procurement for later use.")
        multiplier = (data or {}).get("multiplier") or 1
        payload = {"items": items, "multiplier": multiplier}
        preload_key = uuid4().hex
        cache.set(f"procurement_preload:{request.user.company_id}:{request.user.branch_id}:{preload_key}", payload, timeout=60 * 60 * 24)
        return successResponse("Procurement preload saved successfully.", data={"uuid": preload_key, "payload": payload})

    @staticmethod
    def getPreload(preload_key, request):
        data = cache.get(f"procurement_preload:{request.user.company_id}:{request.user.branch_id}:{preload_key}")
        if data is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement preload not found.")
        products = []
        multiplier = qty(data.get("multiplier") or 1)
        for item in data.get("items") or []:
            product_id = item.get("product_id")
            unit_id = item.get("unit_id")
            exists = commonQuery.branchScopedQueryset(
                ProductUnitQuantity,
                {"product_id": product_id, "unit_id": unit_id, "status__in": [0, 1]},
                request,
            ).exists()
            if not exists:
                continue
            matched = PurchaseOrderService.searchProduct({"search": "", "limit": 1000}, request).data
            product = next((row for row in matched if row.get("id") == product_id), None)
            if product:
                product["procurement"] = {
                    "unit_id": unit_id,
                    "quantity": qty(item.get("quantity")) * multiplier,
                }
                products.append(product)
        return successResponse("Procurement preload retrieved successfully.", data={"items": products})

    @staticmethod
    def setAsPaid(order_id, request):
        response = PurchaseOrderService.changePaymentStatus(
            order_id,
            {
                "payment_status": PurchaseOrderService.PAYMENT_PAID,
                "reference_number": "",
                "note": "Set as paid from procurement action.",
            },
            request,
        )
        response.message = "The procurement has been marked as paid."
        return response

    @staticmethod
    def changePaymentStatus(order_id, data, request):
        procurement = PurchaseOrderService.orderDetail(order_id, request)
        payment_status = (data.get("payment_status") or "").lower()
        if procurement.get("payment_status") == PurchaseOrderService.PAYMENT_PAID:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "You cannot change the status of an already paid procurement.")
        if payment_status not in [PurchaseOrderService.PAYMENT_PAID, PurchaseOrderService.PAYMENT_UNPAID]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment status must be paid or unpaid.")
        target_paid = money(procurement.get("value")) if payment_status == PurchaseOrderService.PAYMENT_PAID else Decimal("0")
        current_paid = money(procurement.get("paid_amount"))
        diff = target_paid - current_paid
        with transaction.atomic():
            if diff > 0:
                commonQuery.branchScopedQueryset(Provider, {"id": procurement["provider_id"]}, request).update(
                    amount_due=F("amount_due") - float(diff),
                    amount_paid=F("amount_paid") + float(diff),
                )
                AccountingService.reflectEvent(
                    "procurement_from_unpaid_to_paid",
                    diff,
                    name=f"Procurement payment {procurement['name']}",
                    transaction_type="expense",
                    source_type="purchase",
                    source_id=order_id,
                    transaction_date=timezone.now(),
                    description=data.get("note") or "Procurement payment",
                    reference_number=data.get("reference_number") or "",
                    request=request,
                )
            elif diff < 0:
                reverse_amount = abs(diff)
                commonQuery.branchScopedQueryset(Provider, {"id": procurement["provider_id"]}, request).update(
                    amount_due=F("amount_due") + float(reverse_amount),
                    amount_paid=F("amount_paid") - float(reverse_amount),
                )
            commonQuery.updateRecordById(Procurement, order_id, {"payment_status": payment_status}, request=request, tenant_config=True)
        return successResponse("Payment status updated successfully.", data=PurchaseOrderService.orderDetail(order_id, request))

    @staticmethod
    def addProduct(order_id, data, request):
        data = dict(data or {})
        data = PurchaseOrderService.sourceItemsPayload(data)[0] if "items" in data and len(PurchaseOrderService.sourceItemsPayload(data)) == 1 else data
        procurement = commonQuery.findOneRecord(Procurement, order_id, request=request, tenant_config=True)
        if procurement is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement not found.")
        if procurement.get("delivery_status") == PurchaseOrderService.DELIVERY_STOCKED:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unable to add products to a stocked procurement.")
        item = PurchaseOrderService.normalizeProductItem(data, request)
        created = PurchaseOrderService.createOrUpdateProductRow(order_id, item, request)
        PurchaseOrderService.recalculateOrder(order_id, request)
        return successResponse("Procurement product added successfully.", data=created)

    @staticmethod
    def editProduct(order_id, purchase_item_id, data, request):
        procurement = commonQuery.findOneRecord(Procurement, order_id, request=request, tenant_config=True)
        if procurement is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement not found.")
        if procurement.get("delivery_status") == PurchaseOrderService.DELIVERY_STOCKED:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unable to edit products from a stocked procurement.")
        item = commonQuery.findOneRecord(ProcurementsProduct, {"id": purchase_item_id, "procurement_id": order_id}, request=request, tenant_config=True)
        if item is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement product not found.")
        update_data = dict(data or {})
        if update_data.get("product_id") or update_data.get("unit_id") or update_data.get("purchase_price") or update_data.get("quantity"):
            merged = {**item, **update_data}
            update_data = PurchaseOrderService.normalizeProductItem(merged, request)
        updated = commonQuery.updateRecordById(ProcurementsProduct, purchase_item_id, update_data, request=request, tenant_config=True)
        PurchaseOrderService.recalculateOrder(order_id, request)
        return successResponse("Procurement product updated successfully.", data=updated)

    @staticmethod
    def bulkUpdateProducts(order_id, data, request):
        products = PurchaseOrderService.sourceItemsPayload(data)
        if not products:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one product row is required.")
        current_ids = set(
            commonQuery.branchScopedQueryset(ProcurementsProduct, {"procurement_id": order_id}, request)
            .exclude(status=2)
            .values_list("id", flat=True)
        )
        provided_existing = [item.get("purchase_item_id") or item.get("id") for item in products if item.get("purchase_item_id") or item.get("id")]
        missing = [item_id for item_id in provided_existing if item_id not in current_ids]
        if missing:
            raise api_error(400, ErrorCodes.BAD_REQUEST, f"The product with the following ID \"{missing[0]}\" is not initially included on the procurement.")
        with transaction.atomic():
            for item in products:
                purchase_item_id = item.get("purchase_item_id") or item.get("id")
                if purchase_item_id:
                    PurchaseOrderService.editProduct(order_id, purchase_item_id, item, request)
                else:
                    PurchaseOrderService.addProduct(order_id, item, request)
        return successResponse("Procurement products updated successfully.", data=PurchaseOrderService.orderDetail(order_id, request))

    @staticmethod
    def convertedQuantityAndPrice(item, request):
        from_unit = commonQuery.findOneRecord(Unit, item["unit_id"], request=request, tenant_config=True)
        to_unit = commonQuery.findOneRecord(Unit, item["convert_unit_id"], request=request, tenant_config=True)
        if not from_unit or not to_unit:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Source or destination unit not found for conversion.")
        from_val = Decimal(str(from_unit.get("value") or 1))
        to_val = Decimal(str(to_unit.get("value") or 1))
        converted_qty = (from_val * qty(item.get("quantity"))) / to_val
        converted_price = (money(item.get("purchase_price")) * to_val) / from_val
        return converted_qty, converted_price

    @staticmethod
    def recordProcurementStockDeletion(procurement, item, request):
        unit_id = item["unit_id"]
        quantity = qty(item.get("quantity"))
        unit_price = money(item.get("purchase_price"))
        total_price = money(item.get("total_purchase_price"))
        if item.get("convert_unit_id"):
            quantity, unit_price = PurchaseOrderService.convertedQuantityAndPrice(item, request)
            unit_id = item["convert_unit_id"]
            total_price = quantity * unit_price
        ProductStockService.recordStockHistory(
            ProductHistory.ACTION_DELETED,
            {
                "product_id": item["product_id"],
                "procurement_id": procurement["id"],
                "procurement_product_id": item["id"],
                "quantity": quantity,
                "unit_id": unit_id,
                "unit_price": unit_price,
                "total_price": total_price,
                "description": f"Procurement product deleted from {procurement['name']}",
            },
            request,
        )

    @staticmethod
    def deleteProduct(order_id, purchase_item_id, request):
        with transaction.atomic():
            procurement = commonQuery.findOneRecord(Procurement, order_id, request=request, tenant_config=True)
            if procurement is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement not found.")
            item = commonQuery.findOneRecord(ProcurementsProduct, {"id": purchase_item_id, "procurement_id": order_id}, request=request, tenant_config=True)
            if item is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement product not found.")
            if procurement.get("delivery_status") == PurchaseOrderService.DELIVERY_STOCKED:
                PurchaseOrderService.recordProcurementStockDeletion(procurement, item, request)
            elif qty(item.get("available_quantity")) < qty(item.get("quantity")):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Partially received procurement product cannot be deleted. Please use stock adjustment.")
            commonQuery.branchScopedQueryset(
                ProcurementsProduct,
                {"id": purchase_item_id, "procurement_id": order_id},
                request,
            ).delete()
            PurchaseOrderService.recalculateOrder(order_id, request)
        return successResponse("Procurement product deleted successfully.")

    @staticmethod
    def searchProduct(data, request):
        search = (data or {}).get("search") or (data or {}).get("argument") or ""
        limit = int((data or {}).get("limit") or 10)
        queryset = commonQuery.branchScopedQueryset(
            Product,
            {"status__in": [0, 1], "stock_management": "enabled", "type__in": ["dematerialized", "materialized"]},
            request,
        ).exclude(type="grouped")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(sku__icontains=search) | Q(barcode__icontains=search))
        rows = list(queryset.values("id", "name", "sku", "barcode", "tax_group_id", "tax_type").order_by("name")[:limit])
        for row in rows:
            unit_quantities = list(commonQuery.branchScopedQueryset(
                ProductUnitQuantity,
                {"product_id": row["id"], "status__in": [0, 1]},
                request,
            ).values("id", "quantity", "cogs", "unit_id", "unit__name", "convert_unit_id").order_by("id"))
            unit_quantity = unit_quantities[0] if unit_quantities else None
            row["unit_quantity_id"] = unit_quantity.get("id") if unit_quantity else None
            row["current_stock"] = unit_quantity.get("quantity") if unit_quantity else 0
            row["purchase_price"] = unit_quantity.get("cogs") if unit_quantity else 0
            row["unit_id"] = unit_quantity.get("unit_id") if unit_quantity else None
            row["unit_name"] = unit_quantity.get("unit__name") if unit_quantity else None
            row["unit_quantities"] = [
                {**unit, "unit": {"id": unit.get("unit_id"), "name": unit.get("unit__name")}, "last_purchase_price": PurchaseOrderService.lastPurchasePrice(row["id"], unit.get("unit_id"), request)}
                for unit in unit_quantities
            ]
            row["purchase_units"] = [{"id": unit.get("unit_id"), "name": unit.get("unit__name")} for unit in unit_quantities]
        return successResponse("Products retrieved successfully.", data=rows)

    @staticmethod
    def searchProcurementProduct(data, request):
        argument = (data or {}).get("argument") or (data or {}).get("search") or ""
        products = PurchaseOrderService.searchProduct({"search": argument, "limit": 8}, request).data
        if products:
            return successResponse("Procurement product search completed successfully.", data={"from": "products", "products": products})
        row = commonQuery.branchScopedQueryset(
            ProcurementsProduct,
            {"status__in": [0, 1], "barcode": argument},
            request,
        ).values("id", "procurement_id", "procurement__name", "product_id", "product__name", "name", "quantity", "available_quantity", "purchase_price", "barcode", "unit_id", "unit__name").first()
        if row:
            row["purchase_order_id"] = row.get("procurement_id")
            row["purchase_order__code"] = row.pop("procurement__name", None)
            row["ordered_quantity"] = row.get("quantity")
            row["received_quantity"] = qty(row.get("quantity")) - qty(row.get("available_quantity"))
            row["cost_price"] = row.get("purchase_price")
            row["unit"] = {"id": row.get("unit_id"), "name": row.get("unit__name")}
            row["unit_quantity"] = commonQuery.findOneRecord(
                ProductUnitQuantity,
                {"product_id": row.get("product_id"), "unit_id": row.get("unit_id")},
                request=request,
                tenant_config=True,
            )
        return successResponse("Procurement product search completed successfully.", data={"from": "procurements", "product": row})

    @staticmethod
    def lastPurchasePrice(product_id, unit_id, request):
        row = commonQuery.branchScopedQueryset(
            ProcurementsProduct,
            {"product_id": product_id, "unit_id": unit_id, "status__in": [0, 1]},
            request,
        ).order_by("-created_at", "-id").values("purchase_price").first()
        return row.get("purchase_price") if row else 0

    @staticmethod
    def delete(data, request):
        ids = data.get("ids")
        if not isinstance(ids, list):
            ids = [ids]
        with transaction.atomic():
            procurements = list(
                commonQuery.branchScopedQueryset(Procurement, {"id__in": ids}, request)
                .exclude(status=2)
                .values("id", "name", "provider_id", "delivery_status")
            )
            for procurement in procurements:
                products = commonQuery.findAllRecords(
                    ProcurementsProduct,
                    {"procurement_id": procurement["id"]},
                    {
                        "attributes": [
                            "id",
                            "product_id",
                            "quantity",
                            "available_quantity",
                            "unit_id",
                            "convert_unit_id",
                            "purchase_price",
                            "total_purchase_price",
                        ]
                    },
                    request=request,
                    tenant_config=True,
                )
                for item in products:
                    if procurement.get("delivery_status") == PurchaseOrderService.DELIVERY_STOCKED:
                        PurchaseOrderService.recordProcurementStockDeletion(procurement, item, request)
                    elif qty(item.get("available_quantity")) < qty(item.get("quantity")):
                        raise api_error(400, ErrorCodes.BAD_REQUEST, "Partially received procurement cannot be deleted. Please use stock adjustment.")
                commonQuery.branchScopedQueryset(
                    ProcurementsProduct,
                    {"procurement_id": procurement["id"]},
                    request,
                ).delete()
                AccountingService.deleteProcurementTransactions(procurement["id"], request)

            count = commonQuery.softDeleteById(Procurement, ids, request=request, tenant_config=True)
            if count == 0:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Procurement not found.")
            for provider_id in {procurement["provider_id"] for procurement in procurements if procurement.get("provider_id")}:
                SupplierService.computeSummary(provider_id, request)
        return successResponse("Procurements deleted successfully.")

    @staticmethod
    def jobHandlers():
        return {
            "refresh_procurement": lambda data, job: PurchaseOrderService.refresh(
                data.get("procurement_id") or data.get("order_id"),
                PurchaseOrderService.requestFromJob(job),
            ),
            "stock_awaiting_procurements": lambda data, job: PurchaseOrderService.stockAwaitingProcurements(
                PurchaseOrderService.requestFromJob(job),
            ),
            "compute_provider_summary": lambda data, job: SupplierService.computeSummary(
                data.get("provider_id") or data.get("supplier_id"),
                PurchaseOrderService.requestFromJob(job),
            ),
        }
