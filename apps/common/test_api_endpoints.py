# type: ignore
import json
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import Permission

from apps.accounts.models import User, Role, AccessToken
from apps.organizations.models import Company, Branch
from apps.accounting.models import TransactionAccount
from apps.catalog.models import Category
from apps.customers.models import CUSTOMER_ROLE_CODE
from apps.customers.models import CustomerCoupon, CustomerReward
from apps.promotions.models import Coupon
from apps.rewards.models import RewardSystem
from apps.sales.models import Order, OrderInstalment
from apps.settings.models import Media


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
        p_pos_categories, _ = Permission.objects.get_or_create(
            codename="pos.read.categories",
            content_type=content_type,
            defaults={"name": "Can read POS categories"},
        )
        p_pos_orders, _ = Permission.objects.get_or_create(
            codename="pos.read.orders",
            content_type=content_type,
            defaults={"name": "Can read POS orders"},
        )
        p_pos_order_instalments, _ = Permission.objects.get_or_create(
            codename="pos.read.orders-instalments",
            content_type=content_type,
            defaults={"name": "Can read POS order instalments"},
        )
        p_settings_view, _ = Permission.objects.get_or_create(
            codename="settings_view",
            content_type=content_type,
            defaults={"name": "Can view settings"},
        )
        p_settings_update, _ = Permission.objects.get_or_create(
            codename="settings_update",
            content_type=content_type,
            defaults={"name": "Can update settings"},
        )
        # Ensure expenses_create permission also exists in the test DB
        Permission.objects.get_or_create(
            codename="expenses_create",
            content_type=content_type,
            defaults={"name": "Can create expenses"},
        )
        self.role_a.permissions.add(p_view)
        self.role_a.permissions.add(p_pos_categories)
        self.role_a.permissions.add(p_pos_orders)
        self.role_a.permissions.add(p_pos_order_instalments)
        self.role_a.permissions.add(p_settings_view)
        self.role_a.permissions.add(p_settings_update)

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

    def test_pos_categories_route_does_not_parse_pos_as_category_id(self):
        Category.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Food",
            displays_on_pos=True,
            status=0,
        )

        response = self.client.get("/api/catalog/categories/pos", **self.headers_a)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertIn("categories", payload["data"])

    def test_sale_refund_receipt_route_does_not_parse_refunds_as_order_id(self):
        response = self.client.get("/api/sales/refunds/1/receipt", **self.headers_a)

        self.assertNotEqual(response.status_code, 422)
        payload = response.json()
        self.assertFalse(payload["success"])
        errors = (payload.get("data") or {}).get("errors", {})
        self.assertNotIn("sale_order_id", errors)

    def test_sale_instalments_endpoint_lists_order_instalments_like_source(self):
        order = Order.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            code="ORD-1",
            customer=self.user_a,
            payment_status="partially_paid",
            total=100,
            tendered_amount=50,
            status=0,
        )
        OrderInstalment.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            sale_order=order,
            amount=50,
            paid=False,
            date=timezone.now(),
            status=0,
        )

        response = self.client.post(
            "/api/sales/instalments/get-transactions",
            data=json.dumps({"page": 1, "limit": 10}),
            content_type="application/json",
            **self.headers_a,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["total"], 1)
        item = payload["data"]["items"][0]
        self.assertEqual(item["order_code"], "ORD-1")
        self.assertIn("customer", item)
        self.assertIn("paid", item)

    def test_source_medias_endpoint_returns_gallery_sizes_and_user_like_source(self):
        Media.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="store-logo",
            extension="png",
            slug="2026/06/store-logo",
            status=0,
        )

        response = self.client.get("/api/medias/?page=1&per_page=20&search=logo", **self.headers_a)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["total"], 1)
        item = payload["data"]["items"][0]
        self.assertEqual(item["name"], "store-logo")
        self.assertEqual(item["extension"], "png")
        self.assertIn("original", item["sizes"])
        self.assertIn("thumb", item["sizes"])
        self.assertEqual(item["user"]["username"], "user_a")

    def test_customer_account_history_source_routes_create_and_list_transactions(self):
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Role)
        read_customers, _ = Permission.objects.get_or_create(
            codename="pos.read.customers",
            content_type=content_type,
            defaults={"name": "Can read customers"},
        )
        manage_history, _ = Permission.objects.get_or_create(
            codename="pos.customers.manage-account-history",
            content_type=content_type,
            defaults={"name": "Can manage customer account history"},
        )
        self.role_a.permissions.add(read_customers)
        self.role_a.permissions.add(manage_history)
        customer_role = Role.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Store Customer",
            namespace=CUSTOMER_ROLE_CODE,
            status=0,
        )
        customer = User.objects.create_user(
            username="customer-a",
            email="customer-a@example.com",
            password="password123",
            company=self.company_a,
            branch=self.branch_a,
            role=customer_role,
            first_name="Customer",
            last_name="A",
            account_amount=0,
            status=0,
        )

        response = self.client.post(
            f"/api/customers/{customer.id}/crud/account-history",
            data=json.dumps({"general": {"operation": "add", "amount": 25, "description": "Opening balance"}}),
            content_type="application/json",
            **self.headers_a,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["operation"], "add")
        self.assertEqual(payload["data"]["description"], "Opening balance")

        list_response = self.client.get(
            f"/api/customers/{customer.id}/account-history?page=1&limit=20",
            **self.headers_a,
        )

        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.json()
        self.assertTrue(list_payload["success"])
        self.assertEqual(list_payload["data"]["total"], 1)
        self.assertEqual(list_payload["data"]["items"][0]["next_amount"], 25.0)

    def test_generated_customer_coupon_source_routes_list_and_update(self):
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Role)
        promotions_view, _ = Permission.objects.get_or_create(
            codename="promotions_view",
            content_type=content_type,
            defaults={"name": "Can view promotions"},
        )
        promotions_update, _ = Permission.objects.get_or_create(
            codename="promotions_update",
            content_type=content_type,
            defaults={"name": "Can update promotions"},
        )
        self.role_a.permissions.add(promotions_view)
        self.role_a.permissions.add(promotions_update)
        coupon = Coupon.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Reward Coupon",
            code="REWARD",
            type="flat_discount",
            discount_value=5,
            status=0,
        )
        customer_coupon = CustomerCoupon.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            coupon=coupon,
            customer=self.user_a,
            name="Generated Coupon",
            code="REWARD-1",
            usage=0,
            limit_usage=1,
            status=0,
        )

        list_response = self.client.post(
            "/api/promotions/customers/coupons-generated/get-transactions",
            data=json.dumps({"page": 1, "limit": 10}),
            content_type="application/json",
            **self.headers_a,
        )

        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.json()
        self.assertTrue(list_payload["success"])
        self.assertEqual(list_payload["data"]["total"], 1)

        update_response = self.client.put(
            f"/api/promotions/customers/coupons-generated/{customer_coupon.id}",
            data=json.dumps({"name": "Updated Coupon", "usage": 1, "limit_usage": 2}),
            content_type="application/json",
            **self.headers_a,
        )

        self.assertEqual(update_response.status_code, 200)
        update_payload = update_response.json()
        self.assertTrue(update_payload["success"])
        self.assertEqual(update_payload["data"]["name"], "Updated Coupon")
        self.assertEqual(update_payload["data"]["usage"], 1)

    def test_customer_reward_source_route_updates_points_and_target_only(self):
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Role)
        rewards_view, _ = Permission.objects.get_or_create(
            codename="rewards_view",
            content_type=content_type,
            defaults={"name": "Can view rewards"},
        )
        rewards_update, _ = Permission.objects.get_or_create(
            codename="rewards_update",
            content_type=content_type,
            defaults={"name": "Can update rewards"},
        )
        self.role_a.permissions.add(rewards_view)
        self.role_a.permissions.add(rewards_update)
        customer_role = Role.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Store Customer",
            namespace=CUSTOMER_ROLE_CODE,
            status=0,
        )
        customer = User.objects.create_user(
            username="reward-customer",
            email="reward-customer@example.com",
            password="password123",
            company=self.company_a,
            branch=self.branch_a,
            role=customer_role,
            first_name="Reward",
            last_name="Customer",
            status=0,
        )
        coupon = Coupon.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Reward Coupon",
            code="REWARD-POINTS",
            type="flat_discount",
            discount_value=5,
            status=0,
        )
        reward_system = RewardSystem.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Points",
            coupon=coupon,
            target=100,
            status=0,
        )
        customer_reward = CustomerReward.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            customer=customer,
            reward=reward_system,
            reward_name="Points",
            points=10,
            target=100,
            status=0,
        )

        response = self.client.put(
            f"/api/rewards/customers/{customer.id}/rewards/{customer_reward.id}",
            data=json.dumps({"points": 30, "target": 120}),
            content_type="application/json",
            **self.headers_a,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["points"], 30.0)
        self.assertEqual(payload["data"]["target"], 120.0)
