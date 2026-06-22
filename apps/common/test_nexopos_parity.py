from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase

from apps.accounting.models import TransactionActionRule, TransactionAccount, TransactionHistory
from apps.accounts.models import Role, User
from apps.catalog.models import Category, Product, ProductHistory, ProductUnitQuantity, ScaleRange, Unit, UnitGroup
from apps.customers.models import CustomerCoupon, CustomerGroup, CustomerReward
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
from apps.sales.models import Order, OrderPayment, OrdersProduct, OrdersProductsRefund, OrdersRefund
from apps.sales.services import SaleService
from apps.settings.models import Job, Option, PaymentType
from apps.settings.services import JobQueueService


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
        self.unit_quantity.refresh_from_db()

        self.assertEqual(refund["total"], Decimal("100.00000"))
        self.assertEqual(order.payment_status, "partially_refunded")
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
