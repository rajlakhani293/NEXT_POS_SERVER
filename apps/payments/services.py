from apps.common.responses import successResponse
from apps.payments.models import paymentTypeOptions


class PaymentTypeService:
    @staticmethod
    def dropdownList():
        return successResponse("Payment types retrieved successfully.", data=paymentTypeOptions())
