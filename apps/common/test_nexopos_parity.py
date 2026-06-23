from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase

from apps.accounting.models import TransactionActionRule, TransactionAccount, TransactionHistory
from apps.accounts.models import Role, User
from apps.catalog.models import Category, Product, ProductHistory, ProductUnitQuantity, ScaleRange, Tax, TaxGroup, Unit, UnitGroup
from apps.customers.models import CustomerAccountHistory, CustomerCoupon, CustomerGroup, CustomerReward
from apps.common.tenantDefaults import TenantDefaultsService
from apps.organizations.models import Branch, Company
from apps.promotions.models import OrdersCoupon
from apps.promotions.services import CouponService
from apps.purchases.models import Procurement, ProcurementsProduct, Provider
from apps.purchases.services import PurchaseOrderService
from apps.registers.models import Register, RegistersHistory
from apps.registers.services import RegisterService
from apps.rewards.models import RewardSystem, RewardSystemRule
from apps.rewards.services import CustomerRewardService
from apps.sales.models import Order, OrderPayment, OrderSetting, OrderTax, OrdersProduct, OrdersProductsRefund, OrdersRefund
from apps.sales.services import SaleService
from apps.settings.models import Job, Option, PaymentType
from apps.settings.services import JobQueueService, OptionSettingService


class NexoPosParityFlowTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Parity Store", code="parity-store")
        self.branch = Branch.objects.create(
            company=self.company,
            name="Main Branch",
            code="main-branch",
            is_head_office=True,
        )
        self.user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            company=self.company,
            branch=self.branch,
            status=0,
        )
        self.request = SimpleNamespace(user=self.user)
        TenantDefaultsService.ensureBranchDefaults(self.company, self.branch)

        unit_group = UnitGroup.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Pieces",
        )
        self.unit = Unit.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            group=unit_group,
            name="Piece",
            identifier="piece",
            value=1,
            base_unit=True,
        )
        self.product = Product.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Test Product",
            sku="TP-001",
            type="materialized",
            stock_management="enabled",
            unit_group=unit_group,
        )
        self.category = Category.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Default Category",
        )
        self.product.category = self.category
        self.product.save(update_fields=["category"])
        self.unit_quantity = ProductUnitQuantity.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            product=self.product,
            unit=self.unit,
            quantity=0,
            low_quantity=2,
            sale_price=100,
            cogs=60,
            visible=True,
        )
        self.provider = Provider.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            first_name="Default Provider",
            email="provider@example.com",
        )

    def create_customer(self, *, group=None, username="customer"):
        customer_role = Role.objects.get(
            company=self.company,
            branch=self.branch,
            namespace="store-customer",
        )
        customer = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="customer123",
            company=self.company,
            branch=self.branch,
            role=customer_role,
            group=group,
            full_name=username.title(),
            status=0,
        )
        customer.assignRole("store-customer")
        return customer

    def stock_product(self, quantity=10):
        purchase = PurchaseOrderService.create(
            {
                "provider_id": self.provider.id,
                "payment_status": "paid",
                "products": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "purchase_price": Decimal("60"),
                        "quantity": Decimal(str(quantity)),
                    }
                ],
            },
            self.request,
        ).data
        procurement_item = ProcurementsProduct.objects.get(procurement_id=purchase["id"])
        PurchaseOrderService.receive(
            purchase["id"],
            {"items": [{"purchase_item_id": procurement_item.id, "received_quantity": Decimal(str(quantity))}]},
            self.request,
        )
        self.unit_quantity.refresh_from_db()
        return purchase

    def test_branch_defaults_match_nexopos_seed_counts(self):
        self.assertEqual(Role.objects.filter(company=self.company, branch=self.branch, status=0).count(), 5)
        self.assertEqual(PaymentType.objects.filter(company=self.company, branch=self.branch, status=0).count(), 3)
        self.assertEqual(TransactionAccount.objects.filter(company=self.company, branch=self.branch, status=0).count(), 17)
        self.assertEqual(TransactionActionRule.objects.filter(company=self.company, branch=self.branch, status=0).count(), 12)
        self.assertEqual(ScaleRange.objects.filter(company=self.company, branch=self.branch, status=0).count(), 11)
        self.assertGreaterEqual(Option.objects.filter(company=self.company, branch=self.branch, status=0).count(), 10)

        identifiers = set(
            PaymentType.objects.filter(company=self.company, branch=self.branch, status=0)
            .values_list("identifier", flat=True)
        )
        self.assertEqual(identifiers, {"cash-payment", "bank-payment", "account-payment"})
        options = {
            option.key: option.value
            for option in Option.objects.filter(company=self.company, branch=self.branch, status=0)
        }
        self.assertEqual(options["currency_symbol"], "₹")
        self.assertEqual(options["currency_iso"], "INR")
        self.assertEqual(options["currency_position"], "before")
        self.assertEqual(options["currency_preferred"], "symbol")
        self.assertEqual(options["pos_preferred_price"], "net_prices")
        self.assertEqual(options["pos_vat"], "disabled")

    def test_delivery_order_statuses_and_saved_settings_follow_nexopos(self):
        self.stock_product(4)
        OptionSettingService.ensureOptionValue(
            self.company,
            self.branch,
            "pos_preferred_price",
            "net_prices",
            user=self.user,
        )
        OptionSettingService.ensureOptionValue(
            self.company,
            self.branch,
            "pos_vat",
            "products_vat",
            user=self.user,
        )

        delivery_sale = SaleService.create(
            {
                "order_type": "delivery",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("1"),
                    }
                ],
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("100")}],
            },
            self.request,
        ).data
        delivery_order = Order.objects.get(id=delivery_sale["id"])
        self.assertEqual(delivery_order.process_status, "pending")
        self.assertEqual(delivery_order.delivery_status, "pending")

        saved_settings = {
            setting.key: setting.value
            for setting in OrderSetting.objects.filter(
                company=self.company,
                branch=self.branch,
                sale_order=delivery_order,
            )
        }
        self.assertEqual(
            set(saved_settings.keys()),
            {
                "pos_preferred_price",
                "pos_vat",
                "order_type",
                "discount_type",
                "discount_value",
                "tax_type",
                "tax_group",
                "note_visibility",
            },
        )
        self.assertEqual(saved_settings["order_type"], "delivery")
        self.assertEqual(saved_settings["pos_vat"], "products_vat")

        SaleService.updateProcessingStatus(delivery_order.id, {"status": "ongoing"}, self.request)
        SaleService.updateDeliveryStatus(delivery_order.id, {"status": "delivered"}, self.request)
        delivery_order.refresh_from_db()
        self.assertEqual(delivery_order.process_status, "ongoing")
        self.assertEqual(delivery_order.delivery_status, "delivered")

        takeaway_sale = SaleService.create(
            {
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("1"),
                    }
                ],
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("100")}],
            },
            self.request,
        ).data
        takeaway_order = Order.objects.get(id=takeaway_sale["id"])
        self.assertEqual(takeaway_order.process_status, "not-available")
        self.assertEqual(takeaway_order.delivery_status, "not-available")
        with self.assertRaises(Exception):
            SaleService.updateDeliveryStatus(takeaway_order.id, {"status": "delivered"}, self.request)

    def test_product_vat_is_computed_from_product_tax_group_like_nexopos(self):
        self.unit_quantity.quantity = Decimal("5")
        self.unit_quantity.save(update_fields=["quantity"])
        tax_group = TaxGroup.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="GST 18",
        )
        Tax.objects.create(user=self.user, company=self.company, branch=self.branch, tax_group=tax_group, name="CGST 9", rate=9)
        Tax.objects.create(user=self.user, company=self.company, branch=self.branch, tax_group=tax_group, name="SGST 9", rate=9)
        self.product.tax_group = tax_group
        self.product.tax_type = "exclusive"
        self.product.save(update_fields=["tax_group", "tax_type"])
        OptionSettingService.ensureOptionValue(self.company, self.branch, "pos_vat", "products_vat", user=self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "pos_preferred_price", "net_prices", user=self.user)

        sale = SaleService.create(
            {
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("1"),
                    }
                ],
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("118")}],
            },
            self.request,
        ).data
        order = Order.objects.get(id=sale["id"])
        sale_item = OrdersProduct.objects.get(sale_order=order)

        self.assertEqual(order.total, Decimal("118.00000"))
        self.assertEqual(order.products_tax_value, Decimal("18.00000"))
        self.assertEqual(order.tax_amount, Decimal("18.00000"))
        self.assertEqual(order.total_without_tax, Decimal("100.00000"))
        self.assertEqual(sale_item.tax_amount, Decimal("18.00000"))
        self.assertEqual(sale_item.total, Decimal("118.00000"))

        refund = SaleService.createReturn(
            order.id,
            {
                "return_type": "refund",
                "payment_type": "cash-payment",
                "items": [
                    {
                        "sale_item_id": sale_item.id,
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100"),
                        "condition": "unspoiled",
                    }
                ],
            },
            self.request,
        ).data["return_order"]
        order.refresh_from_db()

        self.assertEqual(refund["tax_amount"], Decimal("18.00000"))
        self.assertEqual(refund["total"], Decimal("118.00000"))
        self.assertEqual(order.payment_status, "refunded")
        self.assertEqual(order.total, Decimal("0.00000"))

    def test_order_level_vat_creates_order_tax_rows_like_nexopos(self):
        self.unit_quantity.quantity = Decimal("5")
        self.unit_quantity.save(update_fields=["quantity"])
        tax_group = TaxGroup.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Order GST 18",
        )
        Tax.objects.create(user=self.user, company=self.company, branch=self.branch, tax_group=tax_group, name="CGST 9", rate=9)
        Tax.objects.create(user=self.user, company=self.company, branch=self.branch, tax_group=tax_group, name="SGST 9", rate=9)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "pos_vat", "flat_vat", user=self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "pos_preferred_price", "net_prices", user=self.user)

        sale = SaleService.create(
            {
                "order_type": "takeaway",
                "tax_group_id": tax_group.id,
                "tax_type": "exclusive",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("1"),
                    }
                ],
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("118")}],
            },
            self.request,
        ).data
        order = Order.objects.get(id=sale["id"])
        tax_rows = list(OrderTax.objects.filter(sale_order=order).order_by("tax_name"))

        self.assertEqual(order.total, Decimal("118.00000"))
        self.assertEqual(order.tax_amount, Decimal("18.00000"))
        self.assertEqual(order.total_without_tax, Decimal("100.00000"))
        self.assertEqual(len(tax_rows), 2)
        self.assertEqual(tax_rows[0].tax_value, Decimal("9.00000"))
        self.assertEqual(tax_rows[1].tax_value, Decimal("9.00000"))

        sale_item = OrdersProduct.objects.get(sale_order=order)
        refund = SaleService.createReturn(
            order.id,
            {
                "return_type": "refund",
                "payment_type": "cash-payment",
                "items": [
                    {
                        "sale_item_id": sale_item.id,
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100"),
                        "condition": "unspoiled",
                    }
                ],
            },
            self.request,
        ).data["return_order"]
        order.refresh_from_db()
        tax_rows = list(OrderTax.objects.filter(sale_order=order).order_by("tax_name"))

        self.assertEqual(refund["tax_amount"], Decimal("18.00000"))
        self.assertEqual(refund["total"], Decimal("118.00000"))
        self.assertEqual(order.payment_status, "refunded")
        self.assertEqual(order.total, Decimal("0.00000"))
        self.assertEqual(order.tax_amount, Decimal("0.00000"))
        self.assertEqual(tax_rows[0].tax_value, Decimal("0.00000"))
        self.assertEqual(tax_rows[1].tax_value, Decimal("0.00000"))

    def test_unpaid_sale_update_rebuilds_items_totals_and_stock_like_nexopos(self):
        self.unit_quantity.quantity = Decimal("5")
        self.unit_quantity.save(update_fields=["quantity"])
        OptionSettingService.ensureOptionValue(self.company, self.branch, "orders_allow_partial", "true", user=self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "customers_credit_enabled", "true", user=self.user)
        customer = self.create_customer(username="unpaid-edit-customer")

        sale = SaleService.create(
            {
                "customer_id": customer.id,
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("1"),
                    }
                ],
                "payments": [],
            },
            self.request,
        ).data
        order = Order.objects.get(id=sale["id"])
        self.assertEqual(order.payment_status, "unpaid")
        self.assertEqual(order.total, Decimal("100.00000"))
        self.unit_quantity.refresh_from_db()
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("5.0"))

        updated = SaleService.update(
            order.id,
            {
                "customer_id": customer.id,
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("2"),
                    }
                ],
                "payments": [],
            },
            self.request,
        ).data
        order.refresh_from_db()
        self.unit_quantity.refresh_from_db()

        self.assertEqual(updated["total"], Decimal("200.00000"))
        self.assertEqual(order.payment_status, "unpaid")
        self.assertEqual(OrdersProduct.objects.filter(sale_order=order).count(), 1)
        self.assertEqual(OrdersProduct.objects.get(sale_order=order).quantity, Decimal("2.00000"))
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("5.0"))

    def test_partially_paid_sale_update_preserves_payments_and_recomputes_stock_like_nexopos(self):
        self.unit_quantity.quantity = Decimal("5")
        self.unit_quantity.save(update_fields=["quantity"])
        OptionSettingService.ensureOptionValue(self.company, self.branch, "orders_allow_partial", "true", user=self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "customers_credit_enabled", "true", user=self.user)
        customer = self.create_customer(username="partial-edit-customer")

        sale = SaleService.create(
            {
                "customer_id": customer.id,
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("1"),
                    }
                ],
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("50")}],
            },
            self.request,
        ).data
        order = Order.objects.get(id=sale["id"])
        payment = OrderPayment.objects.get(sale_order=order)
        self.unit_quantity.refresh_from_db()
        self.assertEqual(order.payment_status, "partially_paid")
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("4.0"))

        updated = SaleService.update(
            order.id,
            {
                "customer_id": customer.id,
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("2"),
                    }
                ],
                "payments": [
                    {
                        "id": payment.id,
                        "payment_type": "cash-payment",
                        "amount": Decimal("50"),
                    }
                ],
            },
            self.request,
        ).data
        order.refresh_from_db()
        self.unit_quantity.refresh_from_db()
        customer.refresh_from_db()

        self.assertEqual(updated["total"], Decimal("200.00000"))
        self.assertEqual(updated["paid_amount"], Decimal("50.00000"))
        self.assertEqual(order.payment_status, "partially_paid")
        self.assertEqual(OrderPayment.objects.filter(sale_order=order).count(), 1)
        self.assertEqual(OrdersProduct.objects.get(sale_order=order).quantity, Decimal("2.00000"))
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("3.0"))
        self.assertEqual(customer.owed_amount, Decimal("150.00000"))

    def test_procurement_sale_and_accounting_side_effects_follow_nexopos_flow(self):
        purchase = PurchaseOrderService.create(
            {
                "provider_id": self.provider.id,
                "payment_status": "unpaid",
                "products": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "purchase_price": Decimal("60"),
                        "quantity": Decimal("10"),
                    }
                ],
            },
            self.request,
        ).data
        procurement = Procurement.objects.get(id=purchase["id"])
        procurement_item = ProcurementsProduct.objects.get(procurement=procurement)

        self.assertEqual(procurement.payment_status, "unpaid")
        self.assertEqual(procurement.value, Decimal("600.00000"))
        self.assertEqual(
            TransactionHistory.objects.filter(
                company=self.company,
                branch=self.branch,
                procurement_id=procurement.id,
                type="procurement_unpaid",
            ).count(),
            2,
        )

        PurchaseOrderService.receive(
            procurement.id,
            {"items": [{"purchase_item_id": procurement_item.id, "received_quantity": Decimal("10")}]},
            self.request,
        )
        self.unit_quantity.refresh_from_db()
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("10.0"))
        self.assertTrue(
            ProductHistory.objects.filter(
                company=self.company,
                branch=self.branch,
                product=self.product,
                operation_type=ProductHistory.ACTION_STOCKED,
            ).exists()
        )

        PurchaseOrderService.changePaymentStatus(
            procurement.id,
            {"payment_status": "paid", "reference_number": "PAY-1"},
            self.request,
        )
        procurement.refresh_from_db()
        self.provider.refresh_from_db()
        self.assertEqual(procurement.payment_status, "paid")
        self.assertEqual(self.provider.amount_due, Decimal("0.00000"))
        self.assertEqual(self.provider.amount_paid, Decimal("600.00000"))
        self.assertEqual(
            TransactionHistory.objects.filter(
                company=self.company,
                branch=self.branch,
                procurement_id=procurement.id,
                type="procurement_from_unpaid_to_paid",
            ).count(),
            2,
        )

        register = RegisterService.getDefaultRegister(self.request)
        RegisterService.openRegister(
            {"register_id": register["id"], "amount": Decimal("0"), "note": "Opening"},
            self.request,
        )

        sale = SaleService.create(
            {
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("2"),
                    }
                ],
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("200")}],
            },
            self.request,
        ).data

        order = Order.objects.get(id=sale["id"])
        self.unit_quantity.refresh_from_db()
        self.assertRegex(order.code, r"^\d{6}-\d{3}$")
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.total, Decimal("200.00000"))
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("8.0"))
        self.assertTrue(OrderPayment.objects.filter(sale_order=order, identifier="cash-payment", value=200).exists())
        self.assertTrue(OrdersProduct.objects.filter(sale_order=order, product=self.product, quantity=2).exists())
        self.assertTrue(
            ProductHistory.objects.filter(
                company=self.company,
                branch=self.branch,
                product=self.product,
                operation_type=ProductHistory.ACTION_SOLD,
            ).exists()
        )
        self.assertGreaterEqual(
            TransactionHistory.objects.filter(
                company=self.company,
                branch=self.branch,
                order_id=order.id,
            ).count(),
            6,
        )
        self.assertTrue(
            RegistersHistory.objects.filter(
                company=self.company,
                branch=self.branch,
                register_id=register["id"],
                order_id=order.id,
            ).exists()
        )

    def test_coupon_target_usage_and_sale_refund_flow_follow_nexopos(self):
        self.stock_product(10)
        customer = self.create_customer(username="coupon-customer")
        coupon = CouponService.create(
            {
                "name": "Product Discount",
                "code": "PRODUCT10",
                "type": "flat_discount",
                "discount_value": Decimal("10"),
                "minimum_cart_value": Decimal("50"),
                "maximum_cart_value": Decimal("500"),
                "limit_usage": 1,
                "product_ids": [self.product.id],
            },
            self.request,
        ).data

        register = RegisterService.getDefaultRegister(self.request)
        RegisterService.openRegister(
            {"register_id": register["id"], "amount": Decimal("0"), "note": "Opening"},
            self.request,
        )
        sale = SaleService.create(
            {
                "customer_id": customer.id,
                "order_type": "takeaway",
                "coupon_codes": ["PRODUCT10"],
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("2"),
                    }
                ],
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("190")}],
            },
            self.request,
        ).data
        order = Order.objects.get(id=sale["id"])
        sale_item = OrdersProduct.objects.get(sale_order=order)

        self.assertRegex(order.code, r"^\d{6}-\d{3}$")
        self.assertEqual(order.total, Decimal("190.00000"))
        self.assertEqual(order.total_coupons, Decimal("10.00000"))
        self.assertTrue(
            OrdersCoupon.objects.filter(
                sale_order=order,
                coupon_id=coupon["id"],
                code="PRODUCT10",
                counted=True,
            ).exists()
        )

        refund_response = SaleService.createReturn(
            order.id,
            {
                "return_type": "refund",
                "payment_type": "cash-payment",
                "items": [
                    {
                        "sale_item_id": sale_item.id,
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100"),
                        "condition": "unspoiled",
                    }
                ],
            },
            self.request,
        ).data
        refund = refund_response["return_order"]
        order.refresh_from_db()
        sale_item.refresh_from_db()
        self.unit_quantity.refresh_from_db()

        self.assertEqual(refund["total"], Decimal("100.00000"))
        self.assertEqual(order.total, Decimal("90.00000"))
        self.assertEqual(order.payment_status, "partially_refunded")
        self.assertEqual(sale_item.quantity, Decimal("1.00000"))
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("9.0"))
        self.assertTrue(OrdersRefund.objects.filter(id=refund["id"], sale_order=order).exists())
        self.assertTrue(OrdersProductsRefund.objects.filter(return_order_id=refund["id"], sale_item=sale_item).exists())
        self.assertTrue(
            ProductHistory.objects.filter(
                product=self.product,
                operation_type=ProductHistory.ACTION_RETURNED,
                order_id=order.id,
            ).exists()
        )

    def test_customer_reward_redeem_and_job_execution_follow_nexopos(self):
        reward_coupon = CouponService.create(
            {
                "name": "Reward Coupon",
                "code": "REWARD50",
                "type": "flat_discount",
                "discount_value": Decimal("50"),
                "minimum_cart_value": Decimal("0"),
                "maximum_cart_value": Decimal("0"),
                "limit_usage": 1,
                "customer_group_ids": [],
                "product_ids": [self.product.id],
            },
            self.request,
        ).data
        reward_system = RewardSystem.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Default Reward",
            coupon_id=reward_coupon["id"],
            target=Decimal("100"),
            description="Earn by cart value",
        )
        RewardSystemRule.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            reward_system=reward_system,
            from_amount=Decimal("100"),
            to_amount=Decimal("500"),
            reward=Decimal("100"),
        )
        group = CustomerGroup.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Reward Group",
            reward_system=reward_system,
        )
        customer = self.create_customer(group=group, username="reward-customer")

        result = CustomerRewardService.earnFromSale(
            {
                "customer_id": customer.id,
                "cart_total": Decimal("120"),
                "sale_order_id": 123,
            },
            self.request,
        ).data
        balance = CustomerReward.objects.get(customer=customer, reward=reward_system)

        self.assertEqual(result["earned_points"], Decimal("100.00000"))
        self.assertEqual(balance.points, Decimal("0.00000"))
        self.assertEqual(CustomerCoupon.objects.filter(customer=customer, coupon_id=reward_coupon["id"]).count(), 1)

        manual = CustomerRewardService.earn(
            {
                "customer_id": customer.id,
                "reward_system_id": reward_system.id,
                "points": Decimal("80"),
            },
            self.request,
        ).data
        self.assertEqual(manual["balance"]["points"], Decimal("80.00000"))
        redeemed = CustomerRewardService.redeem(
            {
                "customer_id": customer.id,
                "reward_system_id": reward_system.id,
                "points": Decimal("50"),
            },
            self.request,
        ).data
        self.assertEqual(redeemed["balance"]["points"], Decimal("30.00000"))

        job = JobQueueService.enqueue(
            "process_sale_reward",
            {
                "customer_id": customer.id,
                "cart_total": "120",
                "sale_order_id": 456,
            },
            request=self.request,
        )
        run_result = JobQueueService.runNext(CustomerRewardService.jobHandlers())
        self.assertEqual(run_result, {"status": "completed", "job_id": job.id})
        self.assertFalse(Job.objects.filter(id=job.id).exists())

    def test_exchange_return_requires_linked_sale_and_reduces_original_order_product(self):
        self.unit_quantity.quantity = Decimal("10")
        self.unit_quantity.save(update_fields=["quantity"])

        first_sale = SaleService.create(
            {
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("1"),
                    }
                ],
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("100")}],
            },
            self.request,
        ).data
        exchange_sale = SaleService.create(
            {
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("1"),
                    }
                ],
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("100")}],
            },
            self.request,
        ).data
        order = Order.objects.get(id=first_sale["id"])
        sale_item = OrdersProduct.objects.get(sale_order=order)

        response = SaleService.createReturn(
            order.id,
            {
                "return_type": "exchange",
                "payment_type": "cash-payment",
                "exchange_sale_id": exchange_sale["id"],
                "items": [
                    {
                        "sale_item_id": sale_item.id,
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100"),
                        "condition": "unspoiled",
                    }
                ],
            },
            self.request,
        ).data
        order.refresh_from_db()
        sale_item.refresh_from_db()

        self.assertEqual(response["difference_amount"], Decimal("0.00000"))
        self.assertEqual(order.payment_status, "refunded")
        self.assertEqual(order.total, Decimal("0.00000"))
        self.assertEqual(sale_item.quantity, Decimal("0.00000"))
        self.assertTrue(OrdersRefund.objects.filter(sale_order=order, payment_method="cash-payment").exists())

    def test_customer_account_payment_and_credit_note_follow_nexopos(self):
        self.unit_quantity.quantity = Decimal("10")
        self.unit_quantity.save(update_fields=["quantity"])
        OptionSettingService.ensureOptionValue(
            self.company,
            self.branch,
            "customers_credit_enabled",
            "yes",
            user=self.user,
        )
        customer = self.create_customer(username="account-customer")
        customer.account_amount = Decimal("150")
        customer.save(update_fields=["account_amount"])

        sale = SaleService.create(
            {
                "customer_id": customer.id,
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("1"),
                    }
                ],
                "payments": [{"payment_type": "account-payment", "amount": Decimal("100")}],
            },
            self.request,
        ).data
        order = Order.objects.get(id=sale["id"])
        sale_item = OrdersProduct.objects.get(sale_order=order)
        customer.refresh_from_db()

        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(customer.account_amount, Decimal("50.00000"))
        self.assertTrue(
            CustomerAccountHistory.objects.filter(
                customer=customer,
                order=order,
                operation="payment",
                amount=Decimal("100"),
            ).exists()
        )

        response = SaleService.createReturn(
            order.id,
            {
                "return_type": "credit_note",
                "items": [
                    {
                        "sale_item_id": sale_item.id,
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100"),
                        "condition": "unspoiled",
                    }
                ],
            },
            self.request,
        ).data
        customer.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(response["return_order"]["payment_method"], "")
        self.assertEqual(order.payment_status, "refunded")
        self.assertEqual(customer.account_amount, Decimal("150.00000"))
        self.assertTrue(
            CustomerAccountHistory.objects.filter(
                customer=customer,
                order=order,
                operation="refund",
                amount=Decimal("100"),
            ).exists()
        )

    def test_partial_sale_installments_collect_due_and_customer_ledger_follow_nexopos(self):
        self.unit_quantity.quantity = Decimal("10")
        self.unit_quantity.save(update_fields=["quantity"])
        OptionSettingService.ensureOptionValue(
            self.company,
            self.branch,
            "orders_allow_partial",
            "yes",
            user=self.user,
        )
        OptionSettingService.ensureOptionValue(
            self.company,
            self.branch,
            "customers_credit_enabled",
            "yes",
            user=self.user,
        )
        customer = self.create_customer(username="installment-customer")

        sale = SaleService.create(
            {
                "customer_id": customer.id,
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("2"),
                    }
                ],
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("50")}],
            },
            self.request,
        ).data
        order = Order.objects.get(id=sale["id"])
        customer.refresh_from_db()
        self.unit_quantity.refresh_from_db()

        self.assertEqual(order.payment_status, "partially_paid")
        self.assertEqual(order.total, Decimal("200.00000"))
        self.assertEqual(order.tendered_amount, Decimal("50.00000"))
        self.assertEqual(customer.owed_amount, Decimal("150.00000"))
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("8.0"))

        SaleService.createInstallments(
            order.id,
            {
                "total_installments": 1,
                "total_amount": Decimal("150"),
                "lines": [{"due_date": "2026-07-01T00:00:00Z", "amount": Decimal("150")}],
            },
            self.request,
        )
        installment = order.instalments.get()

        SaleService.payInstallment(
            order.id,
            installment.id,
            {
                "amount": Decimal("150"),
                "payment_type": "cash-payment",
                "note": "Final installment",
            },
            self.request,
        )
        order.refresh_from_db()
        customer.refresh_from_db()
        installment.refresh_from_db()
        self.unit_quantity.refresh_from_db()

        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.tendered_amount, Decimal("200.00000"))
        self.assertTrue(installment.paid)
        self.assertEqual(customer.owed_amount, Decimal("0.00000"))
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("8.0"))
        self.assertTrue(
            CustomerAccountHistory.objects.filter(
                customer=customer,
                order=order,
                operation="payment",
                amount=Decimal("150"),
            ).exists()
        )

    def test_unpaid_sale_void_reverses_stock_and_customer_due_like_nexopos(self):
        self.unit_quantity.quantity = Decimal("10")
        self.unit_quantity.save(update_fields=["quantity"])
        OptionSettingService.ensureOptionValue(
            self.company,
            self.branch,
            "orders_allow_partial",
            "yes",
            user=self.user,
        )
        OptionSettingService.ensureOptionValue(
            self.company,
            self.branch,
            "customers_credit_enabled",
            "yes",
            user=self.user,
        )
        customer = self.create_customer(username="void-customer")

        sale = SaleService.create(
            {
                "customer_id": customer.id,
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("2"),
                    }
                ],
                "payments": [],
            },
            self.request,
        ).data
        order = Order.objects.get(id=sale["id"])
        customer.refresh_from_db()
        self.unit_quantity.refresh_from_db()

        self.assertEqual(order.payment_status, "unpaid")
        self.assertEqual(customer.owed_amount, Decimal("200.00000"))
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("10.0"))

        SaleService.void(order.id, {"note": "Customer cancelled"}, self.request)
        order.refresh_from_db()
        customer.refresh_from_db()
        self.unit_quantity.refresh_from_db()

        self.assertEqual(order.payment_status, "void")
        self.assertEqual(customer.owed_amount, Decimal("0.00000"))
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("10.0"))
        self.assertFalse(
            ProductHistory.objects.filter(
                product=self.product,
                order_id=order.id,
                operation_type=ProductHistory.ACTION_VOID_RETURN,
            ).exists()
        )
        self.assertTrue(
            CustomerAccountHistory.objects.filter(
                customer=customer,
                order=order,
                operation="deduct",
                amount=Decimal("200"),
            ).exists()
        )

    def test_unpaid_sale_delete_reverses_stock_and_customer_due_like_nexopos(self):
        self.unit_quantity.quantity = Decimal("10")
        self.unit_quantity.save(update_fields=["quantity"])
        OptionSettingService.ensureOptionValue(
            self.company,
            self.branch,
            "orders_allow_partial",
            "yes",
            user=self.user,
        )
        OptionSettingService.ensureOptionValue(
            self.company,
            self.branch,
            "customers_credit_enabled",
            "yes",
            user=self.user,
        )
        customer = self.create_customer(username="delete-customer")

        sale = SaleService.create(
            {
                "customer_id": customer.id,
                "order_type": "takeaway",
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("2"),
                    }
                ],
                "payments": [],
            },
            self.request,
        ).data
        order = Order.objects.get(id=sale["id"])
        self.unit_quantity.refresh_from_db()
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("10.0"))

        SaleService.delete({"ids": [order.id]}, self.request)
        order.refresh_from_db()
        customer.refresh_from_db()
        self.unit_quantity.refresh_from_db()

        self.assertEqual(order.status, 2)
        self.assertEqual(customer.owed_amount, Decimal("0.00000"))
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("10.0"))
        self.assertFalse(
            ProductHistory.objects.filter(
                product=self.product,
                order_id=order.id,
                operation_type=ProductHistory.ACTION_RETURNED,
            ).exists()
        )
