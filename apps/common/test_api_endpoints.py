# type: ignore
import json
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import Permission

from apps.accounts.models import User, Role, AccessToken
from apps.organizations.models import Company, Branch
from apps.accounting.models import TransactionAccount


class PosApiIntegrationTest(TestCase):
    def setUp(self):
        # 1. Setup Tenant A
        self.company_a = Company.objects.create(name="Company A", code="company-a")
        self.branch_a = Branch.objects.create(
            company=self.company_a,
            name="Branch A",
            code="branch-a",
            is_head_office=True,
        )
        self.role_a = Role.objects.create(
            company=self.company_a,
            branch=self.branch_a,
            name="Cashier A",
            namespace="cashier-a",
            status=0,
        )
        self.user_a = User.objects.create_user(
            username="user_a",
            email="user_a@example.com",
            password="password123",
            company=self.company_a,
            branch=self.branch_a,
            role=self.role_a,
            status=0,
        )
        # Grant a basic view permission initially
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(Role)
        p_view, _ = Permission.objects.get_or_create(
            codename="expenses_view",
            content_type=content_type,
            defaults={"name": "Can view expenses"},
        )
        # Ensure expenses_create permission also exists in the test DB
        Permission.objects.get_or_create(
            codename="expenses_create",
            content_type=content_type,
            defaults={"name": "Can create expenses"},
        )
        self.role_a.permissions.add(p_view)

        self.token_a = AccessToken.objects.create(
            user=self.user_a,
            token="token_a_12345",
            device_name="Test Device A",
            expires_at=timezone.now() + timezone.timedelta(days=30),
            status=0,
        )
        self.headers_a = {"HTTP_AUTHORIZATION": "Bearer token_a_12345"}

        # 2. Setup Tenant B
        self.company_b = Company.objects.create(name="Company B", code="company-b")
        self.branch_b = Branch.objects.create(
            company=self.company_b,
            name="Branch B",
            code="branch-b",
            is_head_office=True,
        )
        self.role_b = Role.objects.create(
            company=self.company_b,
            branch=self.branch_b,
            name="Cashier B",
            namespace="cashier-b",
            status=0,
        )
        self.user_b = User.objects.create_user(
            username="user_b",
            email="user_b@example.com",
            password="password123",
            company=self.company_b,
            branch=self.branch_b,
            role=self.role_b,
            status=0,
        )
        self.token_b = AccessToken.objects.create(
            user=self.user_b,
            token="token_b_12345",
            device_name="Test Device B",
            expires_at=timezone.now() + timezone.timedelta(days=30),
            status=0,
        )
        self.headers_b = {"HTTP_AUTHORIZATION": "Bearer token_b_12345"}

    def test_unauthenticated_requests_return_401(self):
        # Requesting without authorization header must fail with 401
        response = self.client.get("/api/expenses/categories/dropdown-list")
        self.assertEqual(response.status_code, 401)

    def test_tenant_isolation_list_and_direct_access(self):
        # 1. Create Tenant A Category (mapped to TransactionAccount)
        cat_a = TransactionAccount.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Office Supplies A",
            category_identifier="expenses",
            account="100-exp-officesupplies",
            status=0,
        )

        # 2. Create Tenant B Category
        cat_b = TransactionAccount.objects.create(
            user=self.user_b,
            company=self.company_b,
            branch=self.branch_b,
            name="Rent B",
            category_identifier="expenses",
            account="200-exp-rent",
            status=0,
        )

        # 3. Call GET dropdown list as Tenant A
        response = self.client.get("/api/expenses/categories/dropdown-list", **self.headers_a)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Verify only Tenant A's category is returned
        items = data["data"]
        item_names = [item["name"] for item in items]
        self.assertIn("Office Supplies A", item_names)
        self.assertNotIn("Rent B", item_names)

        # 4. Attempt to query Tenant B's category directly by ID using Tenant A's credentials
        response_direct = self.client.get(f"/api/expenses/categories/{cat_b.id}", **self.headers_a)
        # Should return 404 since it's filtered out of Tenant A's tenant-scoped database view
        self.assertEqual(response_direct.status_code, 404)

    def test_permission_enforcement(self):
        # 1. Attempt to create a category without expenses_create permission
        payload = {"name": "Travel Expense", "description": "Business travel cost"}
        response = self.client.post(
            "/api/expenses/categories/",
            data=json.dumps(payload),
            content_type="application/json",
            **self.headers_a,
        )
        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

        # 2. Grant expenses_create permission to Role A
        p_create = Permission.objects.get(codename="expenses_create")
        self.role_a.permissions.add(p_create)

        # 3. Try again
        response = self.client.post(
            "/api/expenses/categories/",
            data=json.dumps(payload),
            content_type="application/json",
            **self.headers_a,
        )
        self.assertEqual(response.status_code, 200)
        res_data = response.json()
        self.assertTrue(res_data["success"])
        self.assertEqual(res_data["data"]["name"], "Travel Expense")

    def test_validation_errors_format(self):
        # Try to create category with missing "name" field (violating schema constraints)
        payload = {"description": "No name provided"}
        response = self.client.post(
            "/api/expenses/categories/",
            data=json.dumps(payload),
            content_type="application/json",
            **self.headers_a,
        )
        self.assertEqual(response.status_code, 422)
        res_data = response.json()
        self.assertFalse(res_data["success"])
        self.assertEqual(res_data["message"], "Validation failed.")
        self.assertIn("name", res_data["data"]["errors"])
