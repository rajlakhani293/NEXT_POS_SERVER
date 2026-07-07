# type: ignore
import json
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import Permission

from apps.accounts.models import User, Role, AccessToken
from apps.organizations.models import Company, Branch
from apps.accounting.models import TransactionAccount
from apps.catalog.models import Category, Product, ProductUnitQuantity, Tax, TaxGroup, Unit, UnitGroup
from apps.customers.models import CUSTOMER_ROLE_CODE, CustomerGroup
from apps.customers.models import CustomerCoupon, CustomerReward
from apps.promotions.models import Coupon
from apps.purchases.models import Procurement, ProcurementsProduct, Provider
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
        p_pos_deliver_orders, _ = Permission.objects.get_or_create(
            codename="pos.deliver.orders",
            content_type=content_type,
            defaults={"name": "Can deliver POS orders"},
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
        p_media_view, _ = Permission.objects.get_or_create(
            codename="media_view",
            content_type=content_type,
            defaults={"name": "Can view media"},
        )
        p_media_upload, _ = Permission.objects.get_or_create(
            codename="media_upload",
            content_type=content_type,
            defaults={"name": "Can upload media"},
        )
        p_media_update, _ = Permission.objects.get_or_create(
            codename="media_update",
            content_type=content_type,
            defaults={"name": "Can update media"},
        )
        p_media_delete, _ = Permission.objects.get_or_create(
            codename="media_delete",
            content_type=content_type,
            defaults={"name": "Can delete media"},
        )
        p_pos_taxes, _ = Permission.objects.get_or_create(
            codename="pos.read.taxes",
            content_type=content_type,
            defaults={"name": "Can read taxes"},
        )
        p_manage_modules, _ = Permission.objects.get_or_create(
            codename="manage.modules",
            content_type=content_type,
            defaults={"name": "Can manage modules"},
        )
        p_users_view, _ = Permission.objects.get_or_create(
            codename="users_view",
            content_type=content_type,
            defaults={"name": "Can view users"},
        )
        p_users_create, _ = Permission.objects.get_or_create(
            codename="users_create",
            content_type=content_type,
            defaults={"name": "Can create users"},
        )
        p_users_delete, _ = Permission.objects.get_or_create(
            codename="users_delete",
            content_type=content_type,
            defaults={"name": "Can delete users"},
        )
        p_roles_view, _ = Permission.objects.get_or_create(
            codename="roles_view",
            content_type=content_type,
            defaults={"name": "Can view roles"},
        )
        p_roles_create, _ = Permission.objects.get_or_create(
            codename="roles_create",
            content_type=content_type,
            defaults={"name": "Can create roles"},
        )
        p_roles_update, _ = Permission.objects.get_or_create(
            codename="roles_update",
            content_type=content_type,
            defaults={"name": "Can update roles"},
        )
        p_roles_delete, _ = Permission.objects.get_or_create(
            codename="roles_delete",
            content_type=content_type,
            defaults={"name": "Can delete roles"},
        )
        p_manage_profile, _ = Permission.objects.get_or_create(
            codename="manage.profile",
            content_type=content_type,
            defaults={"name": "Can manage profile"},
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
        self.role_a.permissions.add(p_pos_deliver_orders)
        self.role_a.permissions.add(p_pos_order_instalments)
        self.role_a.permissions.add(p_settings_view)
        self.role_a.permissions.add(p_settings_update)
        self.role_a.permissions.add(p_media_view)
        self.role_a.permissions.add(p_media_upload)
        self.role_a.permissions.add(p_media_update)
        self.role_a.permissions.add(p_media_delete)
        self.role_a.permissions.add(p_pos_taxes)
        self.role_a.permissions.add(p_manage_modules)
        self.role_a.permissions.add(p_users_view)
        self.role_a.permissions.add(p_users_create)
        self.role_a.permissions.add(p_users_delete)
        self.role_a.permissions.add(p_roles_view)
        self.role_a.permissions.add(p_roles_create)
        self.role_a.permissions.add(p_roles_update)
        self.role_a.permissions.add(p_roles_delete)
        self.role_a.permissions.add(p_manage_profile)

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

    def test_auth_register_login_and_failed_login_flow(self):
        register_response = self.client.post(
            "/api/auth/sign-up",
            data=json.dumps(
                {
                    "username": "source_signup_owner",
                    "email": "source-signup-owner@example.com",
                    "password": "password123",
                    "password_confirm": "password123",
                    "device_name": "Web App",
                }
            ),
            content_type="application/json",
        )
        failed_login_response = self.client.post(
            "/api/auth/sign-in",
            data=json.dumps(
                {
                    "username": "source_signup_owner",
                    "password": "wrong-password",
                    "device_name": "Web App",
                }
            ),
            content_type="application/json",
        )
        login_response = self.client.post(
            "/api/auth/sign-in",
            data=json.dumps(
                {
                    "username": "source_signup_owner",
                    "password": "password123",
                    "device_name": "Web App",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(register_response.status_code, 200, register_response.content.decode())
        self.assertIn("token", register_response.json()["data"])
        self.assertEqual(failed_login_response.status_code, 401)
        self.assertFalse(failed_login_response.json()["success"])
        self.assertEqual(login_response.status_code, 200, login_response.content.decode())
        self.assertIn("token", login_response.json()["data"])

    def test_source_password_recovery_flow(self):
        lost_response = self.client.post(
            "/api/auth/password-lost",
            data=json.dumps({"email": "user_a@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(lost_response.status_code, 200, lost_response.content.decode())
        self.user_a.refresh_from_db()
        self.assertTrue(self.user_a.activation_token)

        invalid_password_response = self.client.post(
            f"/api/auth/new-password/{self.user_a.id}/{self.user_a.activation_token}",
            data=json.dumps({"password": "password456", "password_confirm": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(invalid_password_response.status_code, 422)

        new_password_response = self.client.post(
            f"/api/auth/new-password/{self.user_a.id}/{self.user_a.activation_token}",
            data=json.dumps({"password": "password456", "password_confirm": "password456"}),
            content_type="application/json",
        )
        self.assertEqual(new_password_response.status_code, 200, new_password_response.content.decode())
        self.user_a.refresh_from_db()
        self.assertTrue(self.user_a.check_password("password456"))
        self.assertIsNone(self.user_a.activation_token)

    def test_source_account_activation_flow(self):
        self.user_a.status = 1
        self.user_a.is_active = False
        self.user_a.activation_token = "activate-token"
        self.user_a.activation_expiration = timezone.now() + timezone.timedelta(minutes=30)
        self.user_a.save(update_fields=["status", "is_active", "activation_token", "activation_expiration"])

        invalid_response = self.client.get(f"/api/auth/activate/{self.user_a.id}/wrong-token")
        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.json()["message"], "Invalid activation token.")

        activate_response = self.client.get(f"/api/auth/activate/{self.user_a.id}/activate-token")
        self.assertEqual(activate_response.status_code, 200, activate_response.content.decode())
        self.assertEqual(activate_response.json()["message"], "Your account is now activated.")
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.status, 0)
        self.assertTrue(self.user_a.is_active)
        self.assertIsNone(self.user_a.activation_token)
        self.assertIsNone(self.user_a.activation_expiration)

        already_active_response = self.client.get(f"/api/auth/activate/{self.user_a.id}/activate-token")
        self.assertEqual(already_active_response.status_code, 400)
        self.assertEqual(already_active_response.json()["message"], "No activation is needed for this account.")

        self.user_b.status = 1
        self.user_b.is_active = False
        self.user_b.activation_token = "expired-token"
        self.user_b.activation_expiration = timezone.now() - timezone.timedelta(minutes=1)
        self.user_b.save(update_fields=["status", "is_active", "activation_token", "activation_expiration"])
        expired_response = self.client.get(f"/api/auth/activate/{self.user_b.id}/expired-token")
        self.assertEqual(expired_response.status_code, 400)
        self.assertEqual(expired_response.json()["message"], "The expiration token has expired.")

    def test_source_profile_and_token_flow(self):
        profile_response = self.client.post(
            "/api/users/profile",
            data=json.dumps(
                {
                    "username": "user_a",
                    "full_name": "Updated Profile",
                    "email": "updated-profile@example.com",
                    "phone": "9191919191",
                    "theme": "dark",
                    "language": "fr",
                    "avatar_link": "https://example.com/avatar.png",
                    "billing": {
                        "first_name": "Bill",
                        "last_name": "Profile",
                        "phone": "1112223333",
                        "address_1": "Billing Street",
                        "city": "Billing City",
                        "company": "Billing Company",
                        "email": "billing@example.com",
                    },
                    "shipping": {
                        "first_name": "Ship",
                        "last_name": "Profile",
                        "phone": "4445556666",
                        "address_1": "Shipping Street",
                        "city": "Shipping City",
                        "company": "Shipping Company",
                        "email": "shipping@example.com",
                    },
                }
            ),
            content_type="application/json",
            **self.headers_a,
        )
        self.assertEqual(profile_response.status_code, 200, profile_response.content.decode())
        profile = profile_response.json()["data"]
        self.assertEqual(profile["full_name"], "Updated Profile")
        self.assertEqual(profile["avatar_link"], "https://example.com/avatar.png")
        self.assertEqual(profile["theme"], "dark")
        self.assertEqual(profile["language"], "fr")
        self.assertEqual(profile["attribute"]["avatar_link"], "https://example.com/avatar.png")
        self.assertEqual(profile["addresses"]["billing"]["first_name"], "Bill")
        self.assertEqual(profile["addresses"]["billing"]["company"], "Billing Company")
        self.assertEqual(profile["addresses"]["shipping"]["first_name"], "Ship")
        self.assertEqual(profile["addresses"]["shipping"]["company"], "Shipping Company")

        token_response = self.client.post(
            "/api/users/create-token",
            data=json.dumps({"name": "Integration Token"}),
            content_type="application/json",
            **self.headers_a,
        )
        self.assertEqual(token_response.status_code, 200, token_response.content.decode())

        tokens_response = self.client.get("/api/users/tokens", **self.headers_a)
        self.assertEqual(tokens_response.status_code, 200, tokens_response.content.decode())
        token_records = tokens_response.json()["data"]
        token_names = [item["name"] for item in token_records]
        self.assertIn("Integration Token", token_names)
        token_id = next(item["id"] for item in token_records if item["name"] == "Integration Token")

        delete_response = self.client.delete(f"/api/users/tokens/{token_id}", **self.headers_a)
        self.assertEqual(delete_response.status_code, 200, delete_response.content.decode())

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

    def test_assigned_orders_endpoint_lists_delivery_orders_for_current_driver(self):
        assigned_order = Order.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            code="DELIVERY-ASSIGNED",
            customer=self.user_a,
            driver=self.user_a,
            order_type="delivery",
            payment_status="unpaid",
            delivery_status="pending",
            total=100,
            status=0,
        )
        Order.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            code="DELIVERY-OTHER",
            customer=self.user_a,
            driver=self.user_b,
            order_type="delivery",
            payment_status="unpaid",
            delivery_status="pending",
            total=50,
            status=0,
        )
        Order.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            code="TAKEAWAY-ASSIGNED",
            customer=self.user_a,
            driver=self.user_a,
            order_type="takeaway",
            payment_status="unpaid",
            delivery_status="not-available",
            total=25,
            status=0,
        )

        response = self.client.post(
            "/api/sales/assigned/get-transactions",
            data=json.dumps({"page": 1, "limit": 10}),
            content_type="application/json",
            **self.headers_a,
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertTrue(payload["success"])
        codes = [item["code"] for item in payload["data"]["items"]]
        self.assertIn(assigned_order.code, codes)
        self.assertNotIn("DELIVERY-OTHER", codes)
        self.assertNotIn("TAKEAWAY-ASSIGNED", codes)

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

        self.assertEqual(list_response.status_code, 200, list_response.content.decode())
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

        self.assertEqual(list_response.status_code, 200, list_response.content.decode())
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

    def test_provider_source_routes_list_procurements_and_products(self):
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Role)
        purchases_view, _ = Permission.objects.get_or_create(
            codename="purchases_view",
            content_type=content_type,
            defaults={"name": "Can view purchases"},
        )
        self.role_a.permissions.add(purchases_view)
        provider = Provider.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            first_name="Provider",
            last_name="A",
            email="provider-a@example.com",
            status=0,
        )
        unit_group = UnitGroup.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Count",
            status=0,
        )
        unit = Unit.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            group=unit_group,
            name="Piece",
            identifier="piece",
            value=1,
            status=0,
        )
        product = Product.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Provider Product",
            sku="PROVIDER-PRODUCT",
            barcode="PROVIDER-PRODUCT",
            status=0,
        )
        procurement = Procurement.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            provider=provider,
            name="PROC-1",
            value=100,
            total_items=1,
            status=0,
        )
        ProcurementsProduct.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            procurement=procurement,
            product=product,
            unit=unit,
            name="Provider Product",
            purchase_price=10,
            quantity=10,
            available_quantity=4,
            total_purchase_price=100,
            status=0,
        )

        list_response = self.client.post(
            "/api/providers/get-transactions",
            data=json.dumps({"page": 1, "limit": 10}),
            content_type="application/json",
            **self.headers_a,
        )
        procurements_response = self.client.post(
            f"/api/providers/{provider.id}/procurements/get-transactions",
            data=json.dumps({"page": 1, "limit": 10}),
            content_type="application/json",
            **self.headers_a,
        )
        products_response = self.client.post(
            f"/api/providers/{provider.id}/products/get-transactions",
            data=json.dumps({"page": 1, "limit": 10}),
            content_type="application/json",
            **self.headers_a,
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(procurements_response.status_code, 200)
        self.assertEqual(products_response.status_code, 200)
        self.assertEqual(list_response.json()["data"]["total"], 1)
        self.assertEqual(procurements_response.json()["data"]["total"], 1)
        product_item = products_response.json()["data"]["items"][0]
        self.assertEqual(product_item["procurement_name"], "PROC-1")
        self.assertEqual(product_item["received_quantity"], "6.0")

    def test_accounting_settings_source_options_save_and_load(self):
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Role)
        reports_view, _ = Permission.objects.get_or_create(
            codename="reports_view",
            content_type=content_type,
            defaults={"name": "Can view reports"},
        )
        settings_update, _ = Permission.objects.get_or_create(
            codename="settings_update",
            content_type=content_type,
            defaults={"name": "Can update settings"},
        )
        self.role_a.permissions.add(reports_view)
        self.role_a.permissions.add(settings_update)
        expense_account = TransactionAccount.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Expense Account",
            account="5000-expense",
            category_identifier="expenses",
            status=0,
        )
        asset_account = TransactionAccount.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Cash Account",
            account="1000-cash",
            category_identifier="assets",
            status=0,
        )

        payload = {
            "expense_account_ids": [expense_account.id],
            "paid_expense_offset_account_id": asset_account.id,
            "sales_revenue_account_id": asset_account.id,
            "order_cash_account_id": asset_account.id,
            "receivable_account_id": asset_account.id,
            "cogs_account_id": expense_account.id,
            "inventory_account_id": asset_account.id,
            "procurement_cash_account_id": asset_account.id,
            "procurement_payable_account_id": asset_account.id,
        }
        update_response = self.client.put(
            "/api/accounting/settings",
            data=json.dumps(payload),
            content_type="application/json",
            **self.headers_a,
        )
        get_response = self.client.get("/api/accounting/settings", **self.headers_a)

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(get_response.status_code, 200)
        data = get_response.json()["data"]
        self.assertEqual(data["expense_account_ids"], [expense_account.id])
        self.assertEqual(data["paid_expense_offset_account_id"], asset_account.id)

    def test_transaction_special_routes_do_not_parse_static_segments_as_ids(self):
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Role)
        expenses_update, _ = Permission.objects.get_or_create(
            codename="expenses_update",
            content_type=content_type,
            defaults={"name": "Can update expenses"},
        )
        expenses_create, _ = Permission.objects.get_or_create(
            codename="expenses_create",
            content_type=content_type,
            defaults={"name": "Can create expenses"},
        )
        self.role_a.permissions.add(expenses_update)
        self.role_a.permissions.add(expenses_create)

        trigger_response = self.client.get("/api/transactions/trigger/1", **self.headers_a)
        reflection_response = self.client.get("/api/transactions/history/1/create-reflection", **self.headers_a)

        self.assertNotEqual(trigger_response.status_code, 422)
        self.assertNotEqual(reflection_response.status_code, 422)
        trigger_errors = (trigger_response.json().get("data") or {}).get("errors", {})
        reflection_errors = (reflection_response.json().get("data") or {}).get("errors", {})
        self.assertNotIn("transaction_id", trigger_errors)
        self.assertNotIn("transaction_id", reflection_errors)

    def test_inventory_source_stock_adjustment_and_stock_flow_records(self):
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Role)
        inventory_view, _ = Permission.objects.get_or_create(
            codename="inventory_view",
            content_type=content_type,
            defaults={"name": "Can view inventory"},
        )
        inventory_adjust, _ = Permission.objects.get_or_create(
            codename="inventory_adjust",
            content_type=content_type,
            defaults={"name": "Can adjust inventory"},
        )
        self.role_a.permissions.add(inventory_view)
        self.role_a.permissions.add(inventory_adjust)
        unit_group = UnitGroup.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Count",
            status=0,
        )
        unit = Unit.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            group=unit_group,
            name="Piece",
            identifier="inventory-piece",
            value=1,
            status=0,
        )
        product = Product.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Inventory Product",
            sku="INVENTORY-PRODUCT",
            barcode="INVENTORY-PRODUCT",
            type="materialized",
            stock_management="enabled",
            status=0,
        )
        ProductUnitQuantity.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            product=product,
            unit=unit,
            quantity=5,
            sale_price=10,
            status=0,
        )

        adjustment_response = self.client.post(
            "/api/inventory/adjustments/",
            data=json.dumps(
                {
                    "products": [
                        {
                            "id": product.id,
                            "adjust_action": "added",
                            "adjust_quantity": 3,
                            "adjust_reason": "Manual stock count",
                            "adjust_unit": {"unit_id": unit.id, "sale_price": 10},
                        }
                    ]
                }
            ),
            content_type="application/json",
            **self.headers_a,
        )
        adjustments_response = self.client.post(
            "/api/inventory/adjustments/get-transactions",
            data=json.dumps({"page": 1, "limit": 10}),
            content_type="application/json",
            **self.headers_a,
        )
        ledger_response = self.client.post(
            "/api/inventory/ledger/get-transactions",
            data=json.dumps({"page": 1, "limit": 10}),
            content_type="application/json",
            **self.headers_a,
        )

        self.assertEqual(adjustment_response.status_code, 200)
        self.assertEqual(adjustments_response.status_code, 200)
        self.assertEqual(ledger_response.status_code, 200)
        self.assertEqual(adjustments_response.json()["data"]["total"], 1)
        item = ledger_response.json()["data"]["items"][0]
        self.assertEqual(item["product_name"], "Inventory Product")
        self.assertEqual(item["operation_type"], "added")
        self.assertEqual(item["before_quantity"], 5.0)
        self.assertEqual(item["after_quantity"], 8.0)

    def test_tax_source_routes_return_groups_and_tax_id_children_like_source(self):
        group = TaxGroup.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="GST",
            description="Goods tax",
            status=0,
        )
        tax = Tax.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            tax_group=group,
            name="CGST",
            rate=8,
            description="Central tax",
            status=0,
        )

        taxes_response = self.client.get("/api/taxes", **self.headers_a)
        groups_response = self.client.get("/api/taxes/groups", **self.headers_a)
        group_response = self.client.get(f"/api/taxes/groups/{group.id}", **self.headers_a)

        self.assertEqual(taxes_response.status_code, 200)
        self.assertEqual(groups_response.status_code, 200)
        self.assertEqual(group_response.status_code, 200)
        self.assertEqual(taxes_response.json()["data"][0]["name"], "CGST")
        group_payload = group_response.json()["data"]
        self.assertEqual(group_payload["name"], "GST")
        self.assertEqual(group_payload["taxes"][0]["tax_id"], tax.id)
        self.assertNotIn("id", group_payload["taxes"][0])

    def test_modules_source_routes_return_counts_and_filters(self):
        list_response = self.client.get("/api/modules", **self.headers_a)
        enabled_response = self.client.get("/api/modules/enabled", **self.headers_a)
        missing_response = self.client.get("/api/modules/unknown-module", **self.headers_a)

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(enabled_response.status_code, 200)
        payload = list_response.json()["data"]
        self.assertIn("modules", payload)
        self.assertIn("total_enabled", payload)
        self.assertIn("total_disabled", payload)
        self.assertIn("total_invalid", payload)
        self.assertEqual(missing_response.status_code, 404)

    def test_users_source_list_and_multi_role_assignment_match_source(self):
        second_role = Role.objects.create(
            company=self.company_a,
            branch=self.branch_a,
            name="Supervisor A",
            namespace="supervisor-a",
            status=0,
        )

        create_response = self.client.post(
            "/api/accounts/users/",
            data=json.dumps(
                {
                    "username": "multi_role_user",
                    "password": "password123",
                    "email": "multi@example.com",
                    "roles": [self.role_a.id, second_role.id],
                    "active": True,
                }
            ),
            content_type="application/json",
            **self.headers_a,
        )
        list_response = self.client.get("/api/users", **self.headers_a)
        self_delete_response = self.client.delete(
            "/api/accounts/users/delete",
            data=json.dumps({"ids": [self.user_a.id]}),
            content_type="application/json",
            **self.headers_a,
        )

        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()["data"]
        role_names = [role["name"] for role in created["roles"]]
        self.assertIn("Cashier A", role_names)
        self.assertIn("Supervisor A", role_names)
        self.assertEqual(list_response.status_code, 200, list_response.content.decode())
        source_users = list_response.json()["data"]
        self.assertIsInstance(source_users, list)
        self.assertIn("username", source_users[0])
        self.assertNotIn("items", list_response.json()["data"])
        self.assertEqual(self_delete_response.status_code, 400)

    def test_customer_and_settings_user_transaction_routes_return_paginated_data(self):
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(Role)
        read_customers, _ = Permission.objects.get_or_create(
            codename="pos.read.customers",
            content_type=content_type,
            defaults={"name": "Can read customers"},
        )
        self.role_a.permissions.add(read_customers)

        customer_role = Role.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Store Customer",
            namespace=CUSTOMER_ROLE_CODE,
            status=0,
        )
        customer_group = CustomerGroup.objects.create(
            user=self.user_a,
            company=self.company_a,
            branch=self.branch_a,
            name="Retail Customers",
        )
        User.objects.create_user(
            username="listing-customer-api",
            email="listing-customer-api@example.com",
            password="password123",
            company=self.company_a,
            branch=self.branch_a,
            role=customer_role,
            group=customer_group,
            first_name="Listing",
            last_name="Customer",
            status=0,
        )

        customers_response = self.client.post(
            "/api/customers/get-transactions",
            data=json.dumps({"page": 1, "limit": 10}),
            content_type="application/json",
            **self.headers_a,
        )
        users_response = self.client.post(
            "/api/accounts/users/get-transactions",
            data=json.dumps({"page": 1, "limit": 10}),
            content_type="application/json",
            **self.headers_a,
        )

        self.assertEqual(customers_response.status_code, 200, customers_response.content.decode())
        self.assertEqual(users_response.status_code, 200, users_response.content.decode())

        customers_payload = customers_response.json()["data"]
        users_payload = users_response.json()["data"]

        self.assertGreaterEqual(customers_payload["total"], 1)
        self.assertIn("created_at", customers_payload["items"][0])
        self.assertIn("user_username", customers_payload["items"][0])
        self.assertGreaterEqual(users_payload["total"], 1)
        self.assertIn("created_at", users_payload["items"][0])
        self.assertIn("roles_names", users_payload["items"][0])

    def test_roles_source_clone_and_locked_namespace_match_source(self):
        create_response = self.client.post(
            "/api/accounts/roles",
            data=json.dumps(
                {
                    "name": "Floor Manager",
                    "namespace": "",
                    "description": "Handles floor permissions.",
                    "locked": True,
                    "permission_codenames": ["users_view"],
                }
            ),
            content_type="application/json",
            **self.headers_a,
        )

        self.assertEqual(create_response.status_code, 200, create_response.content.decode())
        created = create_response.json()["data"]
        self.assertEqual(created["namespace"], "floor-manager")
        self.assertFalse(created["locked"])
        self.assertIn("users_view", created["permissions"])

        locked_role = Role.objects.create(
            company=self.company_a,
            branch=self.branch_a,
            user=self.user_a,
            name="Locked Manager",
            namespace="locked-manager",
            locked=True,
            status=0,
        )
        update_response = self.client.put(
            f"/api/accounts/roles/{locked_role.id}",
            data=json.dumps({"name": "Locked Manager Updated", "namespace": "changed-manager"}),
            content_type="application/json",
            **self.headers_a,
        )
        locked_role.refresh_from_db()

        self.assertEqual(update_response.status_code, 200, update_response.content.decode())
        self.assertEqual(locked_role.namespace, "locked-manager")

        clone_response = self.client.get(f"/api/users/roles/{created['id']}/clone", **self.headers_a)
        source_list_response = self.client.get("/api/users/roles", **self.headers_a)

        self.assertEqual(clone_response.status_code, 200, clone_response.content.decode())
        clone = clone_response.json()["data"]
        self.assertEqual(clone["name"], "Floor Manager Copy")
        self.assertEqual(clone["namespace"], "floor-manager-copy")
        self.assertIn("users_view", clone["permissions"])
        self.assertEqual(source_list_response.status_code, 200, source_list_response.content.decode())
        self.assertIsInstance(source_list_response.json()["data"], list)
