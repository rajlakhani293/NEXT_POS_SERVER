from django.contrib import admin


class SmartModelAdmin(admin.ModelAdmin):
    list_per_page = 25
    ordering = ("-id",)

    @admin.display(description="Record")
    def display_name(self, obj):
        return str(obj)

    def get_list_display(self, request):  # type: ignore
        fields = ["id", "display_name"]

        for field in [
            "company",
            "branch",
            "status",
            "created_at",
            "updated_at",
        ]:
            if hasattr(self.model, field):
                fields.append(field)

        return tuple(fields)

    def get_list_filter(self, request):
        filters = []

        for field in [
            "status",
            "company",
            "branch",
            "auth_provider",
            "customer_type",
            "entry_type",
            "payment_type",
            "payment_method",
            "register",
            "cashier",
        ]:
            if hasattr(self.model, field):
                filters.append(field)

        return tuple(filters)

    def get_search_fields(self, request):
        search_fields = []

        for field in [
            "name",
            "code",
            "email",
            "phone",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "legal_name",
            "token",
            "reference_type",
            "reason",
        ]:
            if hasattr(self.model, field):
                search_fields.append(field)

        return tuple(search_fields)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = []

        for field in [
            "uuid",
            "created_at",
            "updated_at",
            "deleted_at",
        ]:
            if hasattr(self.model, field):
                readonly_fields.append(field)

        return tuple(readonly_fields)


class TenantModelAdmin(SmartModelAdmin):
    pass
