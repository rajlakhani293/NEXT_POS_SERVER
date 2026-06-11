# type: ignore
from django.db import transaction
from django.utils.text import slugify

from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import serializeModelInstance
from apps.common.responses import successResponse
from apps.payments.models import DEFAULT_PAYMENT_TYPES, LEGACY_PAYMENT_TYPE_ALIASES, PaymentType, paymentTypeValues


class PaymentTypeService:
    @staticmethod
    def normalizeIdentifier(identifier: str, label: str):
        return slugify(identifier or label)

    @staticmethod
    def ensureDefaultPaymentTypes(company, branch):
        seeded = []
        for item in DEFAULT_PAYMENT_TYPES:
            payment_type, created = PaymentType.objects.get_or_create(
                company_id=company.id,
                branch_id=branch.id,
                identifier=item["identifier"],
                defaults={
                    "label": item["label"],
                    "description": item["description"],
                    "is_system": True,
                    "sort_order": item["sort_order"],
                    "status": 0,
                },
            )
            update_fields = []
            if not payment_type.is_system:
                payment_type.is_system = True
                update_fields.append("is_system")
            if payment_type.sort_order != item["sort_order"] and created:
                payment_type.sort_order = item["sort_order"]
                update_fields.append("sort_order")
            if update_fields:
                payment_type.save(update_fields=update_fields)
            seeded.append(serializeModelInstance(payment_type))

        PaymentType.objects.filter(
            company_id=company.id,
            branch_id=branch.id,
            identifier__in=LEGACY_PAYMENT_TYPE_ALIASES.keys(),
            is_system=True,
        ).update(status=2)
        return seeded

    @staticmethod
    def resolvePaymentType(identifier, request, required=True):
        normalized = PaymentTypeService.normalizeIdentifier(
            LEGACY_PAYMENT_TYPE_ALIASES.get(identifier, identifier) or "",
            LEGACY_PAYMENT_TYPE_ALIASES.get(identifier, identifier) or "",
        )
        if not normalized:
            if required:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment type is required.")
            return ""

        payment_type = PaymentType.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            identifier=normalized,
            status=0,
        ).first()
        if payment_type is None:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid payment type.")
        return payment_type.identifier

    @staticmethod
    def dropdownList(request):
        items = (
            PaymentType.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                status=0,
            )
            .order_by("sort_order", "label")
            .values("identifier", "label")
        )
        return successResponse(
            "Payment types retrieved successfully.",
            data=[{"value": item["identifier"], "label": item["label"]} for item in items],
        )

    @staticmethod
    def listPaymentTypes(data, request):
        field_config = [["label", True, True], ["identifier", True, True], ["description", True, False]]
        return commonQuery.fetchPaginatedData(
            PaymentType,
            data,
            field_config,
            {
                "attributes": ["id", "label", "identifier", "description", "is_system", "sort_order", "status"],
                "order": ["sort_order", "label"],
            },
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )

    @staticmethod
    def createPaymentType(data, request):
        identifier = PaymentTypeService.normalizeIdentifier(data.get("identifier") or "", data.get("label") or "")
        if not identifier:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment identifier is required.")
        if identifier in paymentTypeValues():
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Default payment identifiers are reserved.")
        exists = PaymentType.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            identifier=identifier,
        ).exists()
        if exists:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment identifier already exists.")
        return commonQuery.createRecord(
            PaymentType,
            {
                **data,
                "identifier": identifier,
                "is_system": False,
                "sort_order": max(int(data.get("sort_order") or 0), 0),
            },
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )

    @staticmethod
    def getPaymentType(payment_type_id, request):
        payment_type = commonQuery.findOneRecord(
            PaymentType,
            payment_type_id,
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )
        if payment_type is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Payment type not found.")
        return payment_type

    @staticmethod
    def updatePaymentType(payment_type_id, data, request):
        with transaction.atomic():
            payment_type = PaymentType.objects.filter(
                id=payment_type_id,
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                status__in=[0, 1],
            ).first()
            if payment_type is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Payment type not found.")

            if payment_type.is_system:
                identifier = payment_type.identifier
            else:
                identifier = PaymentTypeService.normalizeIdentifier(data.get("identifier") or "", data.get("label") or "")
                if not identifier:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment identifier is required.")
                if identifier in paymentTypeValues():
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Default payment identifiers are reserved.")
                exists = PaymentType.objects.filter(
                    company_id=request.user.company_id,
                    branch_id=request.user.branch_id,
                    identifier=identifier,
                ).exclude(id=payment_type_id).exists()
                if exists:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment identifier already exists.")

            updated = commonQuery.updateRecordById(
                PaymentType,
                payment_type_id,
                {
                    **data,
                    "identifier": identifier,
                    "is_system": payment_type.is_system,
                    "sort_order": max(int(data.get("sort_order") or 0), 0),
                },
                request=request,
                tenant_config={"company_id": True, "branch_id": True},
            )
            if updated is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Payment type not found.")
            return updated

    @staticmethod
    def deletePaymentTypes(data, request):
        ids = data.get("ids") or []
        if PaymentType.objects.filter(
            id__in=ids,
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            is_system=True,
        ).exists():
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Default payment types cannot be deleted.")
        count = commonQuery.softDeleteById(
            PaymentType,
            ids,
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Payment type not found.")
        return {"deleted_count": count}

    @staticmethod
    def updatePaymentTypeStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(
            PaymentType,
            data.get("ids"),
            status,
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Payment type not found.")
        return {"updated_count": count, "status": status}
