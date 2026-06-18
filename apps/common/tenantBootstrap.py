# type: ignore


class TenantBootstrapService:
    @staticmethod
    def ensureCompanyDefaults(company):
        from apps.accounts.services import AccountsService
        from apps.settingsapi.services import OptionSettingService

        OptionSettingService.ensureCompanySettings(company)

    @staticmethod
    def ensureBranchDefaults(company, branch):
        from apps.accounting.services import AccountingService
        from apps.accounts.services import AccountsService
        from apps.payments.services import PaymentTypeService
        from apps.registers.services import RegisterService

        AccountsService.seedDefaultRoles(company, branch)
        PaymentTypeService.ensureDefaultPaymentTypes(company, branch)
        AccountingService.ensureDefaultAccounting(company, branch)
        RegisterService.ensureDefaultRegister(company, branch)

    @staticmethod
    def ensureTenantDefaults(company, branch):
        TenantBootstrapService.ensureCompanyDefaults(company)
        TenantBootstrapService.ensureBranchDefaults(company, branch)
