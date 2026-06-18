# type: ignore
from apps.accounting.services import AccountingService
from apps.accounts.services import AccountsService
from apps.catalog.services import ScaleRangeService
from apps.payments.services import PaymentTypeService
from apps.settingsapi.services import OptionSettingService


class TenantBootstrapService:
    @staticmethod
    def ensureDefaults(company, branch):
        AccountsService.seedDefaultRoles(company, branch)
        PaymentTypeService.ensureDefaultPaymentTypes(company, branch)
        AccountingService.ensureDefaultAccounting(company, branch)
        OptionSettingService.ensureOption(company=company, branch=branch)
        ScaleRangeService.ensureDefaultScaleRanges(company, branch)
