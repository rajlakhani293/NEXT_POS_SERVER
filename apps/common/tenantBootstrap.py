# type: ignore


class TenantBootstrapService:
    @staticmethod
    def ensureCompanyDefaults(company):
        return None

    @staticmethod
    def ensureBranchDefaults(company, branch):
        from apps.accounting.services import AccountingService
        from apps.accounts.services import AccountsService
        from apps.catalog.services import ScaleRangeService
        from apps.payments.services import PaymentTypeService
        from apps.registers.services import RegisterService
        from apps.settingsapi.services import OptionSettingService

        AccountsService.seedDefaultRoles(company, branch)
        PaymentTypeService.ensureDefaultPaymentTypes(company, branch)
        AccountingService.ensureDefaultAccounting(company, branch)
        OptionSettingService.ensureOption(company=company, branch=branch)
        ScaleRangeService.ensureDefaultScaleRanges(company, branch)
        RegisterService.ensureDefaultRegister(company, branch)

    @staticmethod
    def ensureTenantDefaults(company, branch):
        TenantBootstrapService.ensureCompanyDefaults(company)
        TenantBootstrapService.ensureBranchDefaults(company, branch)
