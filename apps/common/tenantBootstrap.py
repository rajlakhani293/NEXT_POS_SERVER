# type: ignore


class TenantBootstrapService:
    @staticmethod
    def ensureCompanyDefaults(company):
        from apps.accounts.services import AccountsService
        from apps.settingsapi.services import BusinessSettingService

        AccountsService.seedDefaultRoles(company)
        BusinessSettingService.ensureCompanySettings(company)

    @staticmethod
    def ensureBranchDefaults(company, branch):
        from apps.accounting.services import AccountingService
        from apps.expenses.services import ExpenseCategoryService
        from apps.payments.services import PaymentTypeService
        from apps.registers.services import RegisterService

        PaymentTypeService.ensureDefaultPaymentTypes(company, branch)
        AccountingService.ensureDefaultAccounting(company, branch)
        ExpenseCategoryService.ensureDefaultCategories(company, branch)
        RegisterService.ensureDefaultRegister(company, branch)

    @staticmethod
    def ensureTenantDefaults(company, branch):
        TenantBootstrapService.ensureCompanyDefaults(company)
        TenantBootstrapService.ensureBranchDefaults(company, branch)
