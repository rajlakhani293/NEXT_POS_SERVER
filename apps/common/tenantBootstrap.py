from apps.common.tenantDefaults import TenantDefaultsService


class TenantBootstrapService:
    @staticmethod
    def ensureDefaults(company, branch):
        return TenantDefaultsService.ensureBranchDefaults(company, branch)
