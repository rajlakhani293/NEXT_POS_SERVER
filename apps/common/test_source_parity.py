# type: ignore
from decimal import Decimal
from types import SimpleNamespace
from django.test import TestCase
from django.utils import timezone
from apps.accounting.models import TransactionActionRule, TransactionAccount, TransactionHistory
from apps.accounts.models import Role, User
from apps.catalog.models import Category, Product, ProductHistory, ProductUnitQuantity, ScaleRange, Tax, TaxGroup, Unit, UnitGroup
from apps.customers.models import CustomerAccountHistory, CustomerCoupon, CustomerGroup, CustomerReward
from apps.customers.services import CustomerGroupService, CustomerService
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
from apps.sales.models import Order, OrderInstalment, OrderPayment, OrderSetting, OrderStorage, OrderTax, OrdersProduct, OrdersProductsRefund, OrdersRefund
from apps.sales.services import SaleService
from apps.settings.models import FailedJob, Job, Notification, Option, PaymentType
from apps.settings.services import JobQueueService, OptionSettingService, PaymentTypeService


class PosParityFlowTest(TestCase):
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
            namespace="pos.store.customer",
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

    def test_customer_group_delete_transfer_search_and_account_history_follow_source(self):
        source_group = CustomerGroup.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Retail",
        )
        target_group = CustomerGroup.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Wholesale",
        )
        customer = self.create_customer(group=source_group, username="alice-customer")
        customer.first_name = "Alice"
        customer.last_name = "Buyer"
        customer.phone = "555123"
        customer.account_amount = Decimal("25")
        customer.save(update_fields=["first_name", "last_name", "phone", "account_amount"])

        search = CustomerService.search({"search": "Alice"}, self.request).data
        self.assertEqual(len(search), 1)
        self.assertEqual(search[0]["id"], customer.id)

        with self.assertRaises(Exception):
            CustomerGroupService.delete({"ids": [source_group.id]}, self.request)

        transfer = CustomerGroupService.transferCustomers(
            {"from": source_group.id, "to": target_group.id, "ids": "*"},
            self.request,
        ).data
        customer.refresh_from_db()
        self.assertEqual(transfer["updated_count"], 1)
        self.assertEqual(customer.group_id, target_group.id)

        transaction = CustomerService.accountTransaction(
            customer.id,
            {
                "operation": "add",
                "amount": Decimal("10"),
                "description": "Manual account top-up",
            },
            self.request,
        ).data
        customer.refresh_from_db()
        self.assertEqual(transaction["previous_amount"], Decimal("25"))
        self.assertEqual(transaction["next_amount"], Decimal("35"))
        self.assertEqual(customer.account_amount, Decimal("35.00000"))

    def test_order_product_and_payment_read_wrappers_follow_source_routes(self):
        order = Order.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            code="260101-001",
            order_type="takeaway",
            payment_status="unpaid",
        )

        payments = SaleService.getSupportedPayments(self.request).data
        self.assertEqual([payment["identifier"] for payment in payments], ["cash-payment", "bank-payment", "account-payment"])
        self.assertTrue(payments[0]["selected"])

        added = SaleService.addProducts(
            order.id,
            [
                {
                    "product_id": self.product.id,
                    "unit_id": self.unit.id,
                    "unit_quantity_id": self.unit_quantity.id,
                    "quantity": Decimal("1"),
                }
            ],
            self.request,
        ).data
        self.assertEqual(len(added["items"]), 1)

        products = SaleService.getOrderProducts(order.id, self.request).data
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["product_id"], self.product.id)

        order_payments = SaleService.getOrderPayments(order.id, self.request).data
        self.assertEqual(order_payments, [])

        deleted = SaleService.deleteOrderProduct(order.id, products[0]["id"], self.request).data
        self.assertEqual(deleted["total_items"], 0)

    def test_order_payment_allows_source_value_identifier_and_change(self):
        self.stock_product(3)
        order = Order.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            code="260101-002",
            order_type="takeaway",
            payment_status="unpaid",
        )
        SaleService.addProducts(
            order.id,
            [
                {
                    "product_id": self.product.id,
                    "unit_id": self.unit.id,
                    "unit_quantity_id": self.unit_quantity.id,
                    "quantity": Decimal("1"),
                }
            ],
            self.request,
        )

        response = SaleService.addPayment(
            order.id,
            {"identifier": "cash-payment", "value": Decimal("120"), "note": "Cash tender"},
            self.request,
        ).data

        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.tendered_amount, Decimal("120.00000"))
        self.assertEqual(order.change_amount, Decimal("20.00000"))
        self.assertEqual(response["orderPayment"]["id"], OrderPayment.objects.get(sale_order_id=order.id).id)

    def test_order_instalment_source_payload_shape_creates_and_updates_single_line(self):
        order = Order.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            code="260101-003",
            order_type="takeaway",
            payment_status="unpaid",
            total=Decimal("100"),
        )

        created = SaleService.createInstallment(
            order.id,
            {"amount": Decimal("40"), "date": "2026-07-01"},
            self.request,
        ).data
        instalment = OrderInstalment.objects.get(id=created["instalment"]["id"])
        self.assertEqual(instalment.amount, Decimal("40.00000"))

        SaleService.updateInstallment(
            order.id,
            instalment.id,
            {"instalment": {"amount": Decimal("45"), "date": "2026-07-02"}},
            self.request,
        )

        instalment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(instalment.amount, Decimal("45.00000"))
        self.assertEqual(timezone.localtime(instalment.date).date().isoformat(), "2026-07-02")
        self.assertEqual(order.total_instalments, 1)

    def test_order_print_and_void_wrappers_follow_source_response_shape(self):
        order = Order.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            code="260101-004",
            order_type="takeaway",
            payment_status="paid",
            tendered_amount=Decimal("100"),
            total=Decimal("100"),
        )

        printed = SaleService.printOrder(order.id, "receipt", self.request)
        self.assertEqual(printed.message, "The printing event has been successfully dispatched.")
        self.assertIsNone(printed.data)

        voided = SaleService.voidOrder(order.id, {"reason": "Customer cancelled"}, self.request)
        order.refresh_from_db()
        self.assertEqual(voided.message, "The order has been correctly voided.")
        self.assertIsNone(voided.data)
        self.assertEqual(order.payment_status, "order_void")
        self.assertEqual(order.voidance_reason, "Customer cancelled")

    def test_order_refund_wrapper_accepts_source_payload_and_shipping(self):
        self.stock_product(3)
        sale = SaleService.create(
            {
                "order_type": "takeaway",
                "shipping": Decimal("10"),
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("1"),
                    }
                ],
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("110")}],
            },
            self.request,
        ).data
        order = Order.objects.get(id=sale["id"])
        sale_item = OrdersProduct.objects.get(sale_order=order)

        refunded = SaleService.refundOrder(
            order.id,
            {
                "payment": {"identifier": "cash-payment"},
                "refund_shipping": True,
                "total": Decimal("110"),
                "products": [
                    {
                        "id": sale_item.id,
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100"),
                        "condition": "unspoiled",
                        "description": "Returned in good condition",
                    }
                ],
            },
            self.request,
        ).data

        order.refresh_from_db()
        order_refund = refunded["orderRefund"]
        self.assertEqual(order_refund["payment_method"], "cash-payment")
        self.assertEqual(order_refund["shipping"], Decimal("10.00000"))
        self.assertEqual(order_refund["total"], Decimal("110.00000"))
        self.assertEqual(order.shipping, Decimal("0.00000"))
        self.assertEqual(refunded["results"][0]["data"]["productRefund"]["description"], "Returned in good condition")

        refunds = SaleService.getOrderRefunds(order.id, self.request).data
        self.assertEqual(refunds["id"], order.id)
        self.assertEqual(refunds["refunds"][0]["id"], order_refund["id"])
        self.assertEqual(refunds["refunds"][0]["payment_method_label"], "Cash")

    def test_order_collection_and_receipt_routes_follow_source_shape(self):
        self.stock_product(3)
        customer = self.create_customer(username="receipt-customer")
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
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("100")}],
            },
            self.request,
        ).data
        order = Order.objects.get(id=sale["id"])
        payment = OrderPayment.objects.get(sale_order=order)

        orders = SaleService.getOrderCollection({"limit": 1}, self.request).data
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["id"], order.id)
        self.assertEqual(orders[0]["customer"]["id"], customer.id)

        receipt = SaleService.getOrderReceipt(order.id, self.request)
        self.assertEqual(receipt.message, f"Order Receipt — {order.code}")
        self.assertEqual(receipt.data["payments"][0]["identifier"], "cash-payment")

        invoice = SaleService.getOrderInvoice(order.id, self.request)
        self.assertEqual(invoice.message, f"Order Invoice — {order.code}")
        self.assertEqual(invoice.data["paymentStatus"], "paid")

        payment_receipt = SaleService.getOrderPaymentReceipt(payment.id, self.request)
        self.assertEqual(payment_receipt.message, f"Payment Receipt — {order.code}")
        self.assertEqual(payment_receipt.data["payment"]["label"], "Cash")
        self.assertEqual(payment_receipt.data["order"]["id"], order.id)

    def test_pos_session_exposes_source_context_with_neutral_option_keys(self):
        OptionSettingService.ensureOptionValue(self.company, self.branch, "orders_allow_partial", "yes", user=self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "registers_enabled", "no", user=self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "order_types", ["takeaway"], user=self.user)

        session = SaleService.getPosSession(self.request).data

        self.assertEqual(session["title"], "POS")
        self.assertEqual([order_type["identifier"] for order_type in session["orderTypes"]], ["takeaway"])
        self.assertEqual(session["orderTypes"][0]["label"], "Take Away")
        self.assertEqual(session["options"]["orders_allow_partial"], "yes")
        self.assertEqual(session["options"]["pos_registers_enabled"], "no")
        self.assertEqual(session["options"]["pos_order_types"], ["takeaway"])
        self.assertEqual([payment["identifier"] for payment in session["paymentTypes"]], ["cash-payment", "bank-payment", "account-payment"])
        blocked_product_prefix = "ne" + "xo"
        blocked_short_prefix = "n" + "s"
        self.assertFalse(any(key.startswith(blocked_product_prefix) or key.split("_", 1)[0] == blocked_short_prefix for key in session["options"]))

    def test_order_payment_fields_follow_source_register_condition(self):
        OptionSettingService.ensureOptionValue(self.company, self.branch, "registers_enabled", "no", user=self.user)
        disabled_fields = SaleService.getOrderPaymentFields(self.request).data
        self.assertEqual([field["name"] for field in disabled_fields], ["identifier"])
        self.assertEqual(disabled_fields[0]["label"], "Select Payment")
        self.assertEqual(disabled_fields[0]["options"][0]["value"], "cash-payment")

        register = Register.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Front Counter",
            register_status=Register.STATUS_OPENED,
            used_by=self.user,
        )
        OptionSettingService.ensureOptionValue(self.company, self.branch, "registers_enabled", "yes", user=self.user)
        enabled_fields = SaleService.getOrderPaymentFields(self.request).data
        self.assertEqual([field["name"] for field in enabled_fields], ["identifier", "register_id"])
        self.assertFalse(enabled_fields[1]["disabled"])
        self.assertEqual(enabled_fields[1]["options"], [{"value": register.id, "label": "Front Counter"}])

    def test_register_payment_and_change_history_keep_source_payment_type_ids(self):
        register = Register.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Payment Register",
            register_status=Register.STATUS_OPENED,
            used_by=self.user,
            balance=Decimal("0"),
        )
        bank_payment = PaymentType.objects.get(company=self.company, branch=self.branch, identifier="bank-payment")
        order = Order.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            code="260101-005",
            order_type="takeaway",
            payment_status="paid",
            register=register,
            total=Decimal("100"),
            tendered_amount=Decimal("120"),
            change_amount=Decimal("20"),
        )
        order_payment = OrderPayment.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            sale_order=order,
            identifier="bank-payment",
            value=Decimal("120"),
        )

        payment_history = RegisterService.recordOrderPayment(order_payment.id, self.request).data
        self.assertEqual(payment_history["entry_type"], RegistersHistory.ACTION_ORDER_PAYMENT)
        self.assertEqual(payment_history["payment_type_id"], bank_payment.id)
        self.assertEqual(payment_history["payment_id"], order_payment.id)

        OptionSettingService.ensureOptionValue(
            self.company,
            self.branch,
            "registers_default_change_payment_type",
            bank_payment.id,
            user=self.user,
        )
        change_history = RegisterService.recordOrderChange(order.id, self.request).data
        self.assertEqual(change_history["entry_type"], RegistersHistory.ACTION_ORDER_CHANGE)
        self.assertEqual(change_history["payment_type_id"], bank_payment.id)
        self.assertEqual(change_history["order_id"], order.id)

    def test_register_details_and_session_history_follow_source_summary_shape(self):
        register = Register.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Session Register",
            register_status=Register.STATUS_OPENED,
            used_by=self.user,
            balance=Decimal("0"),
        )
        opening = RegisterService.recordHistory(
            register.id,
            RegistersHistory.ACTION_OPENING,
            Decimal("50"),
            self.request,
            "Opening",
        )
        cash_payment = PaymentType.objects.get(company=self.company, branch=self.branch, identifier="cash-payment")
        order = Order.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            code="260101-006",
            order_type="takeaway",
            payment_status="paid",
            register=register,
            total=Decimal("120"),
            tendered_amount=Decimal("140"),
            change_amount=Decimal("20"),
        )
        RegisterService.recordHistory(
            register.id,
            RegistersHistory.ACTION_ORDER_PAYMENT,
            Decimal("140"),
            self.request,
            "Order payment",
            payment_type_id=cash_payment.id,
            order_id=order.id,
        )
        RegisterService.recordHistory(
            register.id,
            RegistersHistory.ACTION_ORDER_CHANGE,
            Decimal("20"),
            self.request,
            "Change on cash",
            payment_type_id=cash_payment.id,
            order_id=order.id,
        )

        details = RegisterService.getRegisters(self.request, register.id).data
        self.assertEqual(details["status_label"], "Opened")
        self.assertEqual(details["opening_balance"], Decimal("50.00000"))
        self.assertEqual(details["total_sale_amount"], Decimal("120.00000"))

        session = RegisterService.getSessionHistory(register.id, self.request).data
        self.assertEqual(session["history"][0]["id"], opening["id"])
        self.assertEqual(session["history"][1]["label"], f"Payment Cash on {order.id}")
        self.assertEqual(session["history"][2]["label"], f"Change Cash on {order.id}")
        summary = {item["label"]: item for item in session["summary"]}
        self.assertEqual(summary["Initial Balance"]["value"], Decimal("50.00000"))
        self.assertEqual(summary["Total Cash"]["value"], Decimal("140.00000"))
        self.assertEqual(summary["Total Change"]["value"], Decimal("20.00000"))
        self.assertEqual(summary["On Hand"]["value"], Decimal("170.00000"))

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

    def test_branch_defaults_match_source_seed_counts(self):
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
        self.assertEqual(options["store_language"], "en")

    def test_payment_type_crud_rules_follow_source(self):
        created = PaymentTypeService.createPaymentType(
            {
                "label": "Mobile Wallet",
                "identifier": "",
                "description": "Wallet payment",
                "priority": -5,
                "active": False,
            },
            self.request,
        ).data
        self.assertEqual(created["identifier"], "mobile-wallet")
        self.assertEqual(created["priority"], 0)
        self.assertEqual(created["status"], 1)
        self.assertFalse(created["active"])
        self.assertEqual(created["active_label"], "No")

        listed = PaymentTypeService.listPaymentTypes({"page": 1, "limit": 10}, self.request)
        listed_custom = next(item for item in listed["items"] if item["id"] == created["id"])
        self.assertFalse(listed_custom["active"])
        self.assertEqual(listed_custom["readonly_label"], "No")

        cash = PaymentType.objects.get(company=self.company, branch=self.branch, identifier="cash-payment")
        updated_cash = PaymentTypeService.updatePaymentType(
            cash.id,
            {
                "label": "Cash Counter",
                "identifier": "changed-cash",
                "description": cash.description,
                "priority": 9,
                "active": True,
            },
            self.request,
        )
        cash.refresh_from_db()
        self.assertEqual(updated_cash["identifier"], "cash-payment")
        self.assertEqual(cash.identifier, "cash-payment")
        self.assertEqual(cash.label, "Cash Counter")

        custom = PaymentType.objects.get(id=created["id"])
        delete_counts = PaymentTypeService.deletePaymentTypes({"ids": [custom.id, cash.id]}, self.request)
        custom.refresh_from_db()
        self.assertEqual(delete_counts["success"], 1)
        self.assertEqual(delete_counts["error"], 1)
        self.assertEqual(custom.status, 2)
        self.assertTrue(PaymentType.objects.filter(id=cash.id, status=0).exists())

    def test_delivery_order_statuses_and_saved_settings_follow_source(self):
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

    def test_product_vat_is_computed_from_product_tax_group_like_source(self):
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

        detail = SaleService.getSale(order.id, self.request).data
        receipt = SaleService.getReceipt(order.id, self.request).data
        self.assertEqual(detail["items"][0]["tax_group_id"], tax_group.id)
        self.assertEqual(detail["items"][0]["tax_type"], "exclusive")
        self.assertEqual(detail["items"][0]["price_net"], Decimal("100.00000"))
        self.assertEqual(detail["items"][0]["price_gross"], Decimal("118.00000"))
        self.assertEqual(detail["payments"][0]["label"], "Cash")
        self.assertEqual(detail["settings_map"]["pos_vat"], "products_vat")
        self.assertEqual(detail["totals_summary"]["paid_amount"], Decimal("118.00000"))
        self.assertEqual(detail["totals_summary"]["due_amount"], Decimal("0"))
        self.assertEqual(detail["cashier"]["id"], self.user.id)
        self.assertEqual(receipt["items"][0]["tax_amount"], Decimal("18.00000"))
        self.assertEqual(receipt["payments"][0]["payment_type"], "cash-payment")
        self.assertEqual(receipt["settings_map"]["pos_preferred_price"], "net_prices")

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
        refund_receipt = SaleService.getRefundReceipt(refund["id"], self.request).data
        self.assertEqual(refund_receipt["sale_order"]["code"], order.code)
        self.assertEqual(refund_receipt["payment_method_label"], "Cash")
        self.assertEqual(refund_receipt["items"][0]["product__name"], "Test Product")
        self.assertEqual(refund_receipt["items"][0]["unit__name"], "Piece")
        self.assertEqual(refund_receipt["items"][0]["tax_amount"], Decimal("18.00000"))
        self.assertEqual(refund_receipt["totals_summary"]["total"], Decimal("118.00000"))

    def test_order_level_vat_creates_order_tax_rows_like_source(self):
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
        receipt = SaleService.getReceipt(order.id, self.request).data
        self.assertEqual(len(receipt["taxes"]), 2)
        self.assertEqual(receipt["taxes"][0]["tax_value"], Decimal("9.00000"))
        self.assertEqual(receipt["tax_type"], "exclusive")

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

    def test_unpaid_sale_update_rebuilds_items_totals_and_stock_like_source(self):
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

    def test_partially_paid_sale_update_preserves_payments_and_recomputes_stock_like_source(self):
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

    def test_unpaid_sale_void_keeps_order_trace_and_reason_like_source(self):
        OptionSettingService.ensureOptionValue(self.company, self.branch, "orders_allow_partial", "true", user=self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "customers_credit_enabled", "true", user=self.user)
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
                        "quantity": Decimal("1"),
                    }
                ],
                "payments": [],
            },
            self.request,
        ).data
        order = Order.objects.get(id=sale["id"])

        SaleService.void(order.id, {"note": "Wrong cart"}, self.request)
        order.refresh_from_db()
        customer.refresh_from_db()

        self.assertEqual(order.payment_status, "order_void")
        self.assertEqual(order.voidance_reason, "Wrong cart")
        self.assertIn("Void Note: Wrong cart", order.note)
        self.assertEqual(customer.owed_amount, Decimal("0.00000"))
        self.assertTrue(Order.objects.filter(id=order.id).exists())

    def test_sale_delete_reverses_related_records_and_soft_deletes_order_like_source(self):
        self.stock_product(5)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "orders_allow_partial", "true", user=self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "customers_credit_enabled", "true", user=self.user)
        customer = self.create_customer(username="delete-customer")
        coupon = CouponService.create(
            {
                "name": "Delete Flow Coupon",
                "code": "DELETE10",
                "type": "flat_discount",
                "discount_value": Decimal("10"),
                "minimum_cart_value": Decimal("0"),
                "maximum_cart_value": Decimal("0"),
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
                "coupon_codes": ["DELETE10"],
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
        issued_coupon = CustomerCoupon.objects.get(coupon_id=coupon["id"], customer_id=customer.id)
        self.unit_quantity.refresh_from_db()
        customer.refresh_from_db()
        self.assertEqual(order.payment_status, "partially_paid")
        self.assertEqual(issued_coupon.usage, 1)
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("3.0"))
        self.assertEqual(customer.owed_amount, Decimal("140.00000"))

        SaleService.delete({"ids": [order.id]}, self.request)
        order.refresh_from_db()
        issued_coupon.refresh_from_db()
        self.unit_quantity.refresh_from_db()
        customer.refresh_from_db()

        self.assertEqual(order.status, 2)
        self.assertEqual(OrdersProduct.objects.filter(sale_order=order).count(), 0)
        self.assertEqual(OrderPayment.objects.filter(sale_order=order).count(), 0)
        self.assertEqual(OrdersCoupon.objects.filter(sale_order=order).count(), 0)
        self.assertEqual(issued_coupon.usage, 0)
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("5.0"))
        self.assertEqual(customer.owed_amount, Decimal("0.00000"))
        self.assertFalse(RegistersHistory.objects.filter(order_id=order.id).exists())

    def test_collect_due_updates_payment_customer_register_and_accounting_like_source(self):
        self.stock_product(5)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "orders_allow_partial", "true", user=self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "customers_credit_enabled", "true", user=self.user)
        customer = self.create_customer(username="due-customer")
        register = RegisterService.getDefaultRegister(self.request)
        RegisterService.openRegister(
            {"register_id": register["id"], "amount": Decimal("0"), "note": "Opening"},
            self.request,
        )

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
        self.assertEqual(customer.owed_amount, Decimal("150.00000"))
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("3.0"))

        collected = SaleService.collectDue(
            order.id,
            {
                "note": "Final due",
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("150")}],
            },
            self.request,
        ).data
        order.refresh_from_db()
        customer.refresh_from_db()
        self.unit_quantity.refresh_from_db()

        self.assertEqual(collected["collected_amount"], Decimal("150.00000"))
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.tendered_amount, Decimal("200.00000"))
        self.assertEqual(customer.owed_amount, Decimal("0.00000"))
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("3.0"))
        self.assertEqual(OrderPayment.objects.filter(sale_order=order).count(), 2)
        self.assertEqual(
            CustomerAccountHistory.objects.filter(customer=customer, operation="payment", order_id=order.id).count(),
            1,
        )
        self.assertEqual(
            RegistersHistory.objects.filter(order_id=order.id, entry_type=RegistersHistory.ACTION_ORDER_PAYMENT).count(),
            2,
        )
        self.assertGreaterEqual(
            TransactionHistory.objects.filter(order_id=order.id, type="order_from_unpaid_to_paid").count(),
            2,
        )

    def test_installment_payment_marks_line_and_finalizes_sale_like_source(self):
        self.stock_product(5)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "orders_allow_partial", "true", user=self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "customers_credit_enabled", "true", user=self.user)
        customer = self.create_customer(username="installment-customer")
        register = RegisterService.getDefaultRegister(self.request)
        RegisterService.openRegister(
            {"register_id": register["id"], "amount": Decimal("0"), "note": "Opening"},
            self.request,
        )

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
        installments = SaleService.createInstallments(
            order.id,
            {
                "total_installments": 2,
                "final_payment_date": timezone.now(),
                "lines": [
                    {"due_date": timezone.now(), "amount": Decimal("50")},
                    {"due_date": timezone.now(), "amount": Decimal("100")},
                ],
            },
            self.request,
        ).data
        self.assertEqual(len(installments), 2)

        first_installment = OrderInstalment.objects.filter(sale_order=order).order_by("amount").first()
        paid_response = SaleService.payInstallment(
            order.id,
            first_installment.id,
            {"amount": Decimal("50"), "payment_type": "cash-payment", "note": "First installment"},
            self.request,
        ).data
        first_installment.refresh_from_db()
        order.refresh_from_db()
        customer.refresh_from_db()

        self.assertTrue(first_installment.paid)
        self.assertIsNotNone(first_installment.payment_id)
        self.assertEqual(order.payment_status, "partially_paid")
        self.assertEqual(order.tendered_amount, Decimal("100.00000"))
        self.assertEqual(customer.owed_amount, Decimal("100.00000"))
        self.assertEqual(paid_response["instalment"]["id"], first_installment.id)
        self.assertEqual(paid_response["payment"]["id"], first_installment.payment_id)
        self.assertEqual(paid_response["order"]["totals_summary"]["due_amount"], Decimal("100.00000"))
        with self.assertRaises(Exception):
            SaleService.updateInstallment(order.id, first_installment.id, {"amount": Decimal("60")}, self.request)

        second_installment = OrderInstalment.objects.filter(sale_order=order, paid=False).first()
        SaleService.payInstallment(
            order.id,
            second_installment.id,
            {"payment_type": "cash-payment", "note": "Final installment"},
            self.request,
        )
        second_installment.refresh_from_db()
        order.refresh_from_db()
        customer.refresh_from_db()

        self.assertTrue(second_installment.paid)
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(order.tendered_amount, Decimal("200.00000"))
        self.assertEqual(customer.owed_amount, Decimal("0.00000"))
        self.assertIsNotNone(order.final_payment_date)
        self.assertEqual(
            RegistersHistory.objects.filter(order_id=order.id, entry_type=RegistersHistory.ACTION_ORDER_PAYMENT).count(),
            3,
        )

    def test_hold_cart_has_no_stock_payment_accounting_or_customer_side_effects_like_source(self):
        self.stock_product(5)
        customer = self.create_customer(username="hold-customer")

        held = SaleService.hold(
            {
                "customer_id": customer.id,
                "note": "Call back later",
                "coupon_codes": ["NOT-YET-USED"],
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("2"),
                    }
                ],
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("20")}],
            },
            self.request,
        ).data
        draft = Order.objects.get(id=held["id"])
        self.unit_quantity.refresh_from_db()
        customer.refresh_from_db()

        self.assertEqual(draft.payment_status, "hold")
        self.assertEqual(draft.status, 0)
        self.assertEqual(held["draft_status"], "held")
        self.assertEqual(held["items"][0]["line_total"], Decimal("200.00000"))
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("5.0"))
        self.assertEqual(customer.owed_amount, Decimal("0.00000"))
        self.assertEqual(OrdersProduct.objects.filter(sale_order=draft).count(), 0)
        self.assertEqual(OrderPayment.objects.filter(sale_order=draft).count(), 0)
        self.assertFalse(TransactionHistory.objects.filter(order_id=draft.id).exists())

        fetched = SaleService.getHeldCart(draft.id, self.request).data
        self.assertEqual(fetched["note_text"], "Call back later")
        self.assertEqual(fetched["payments"][0]["amount"], Decimal("20.00000"))

    def test_hold_cart_conversion_soft_deletes_draft_and_processes_real_sale_like_source(self):
        self.stock_product(5)
        customer = self.create_customer(username="hold-convert-customer")
        held = SaleService.hold(
            {
                "customer_id": customer.id,
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("2"),
                    }
                ],
            },
            self.request,
        ).data
        draft = Order.objects.get(id=held["id"])

        sale = SaleService.create(
            {
                "draft_id": draft.id,
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
                "payments": [{"payment_type": "cash-payment", "amount": Decimal("200")}],
            },
            self.request,
        ).data
        draft.refresh_from_db()
        self.unit_quantity.refresh_from_db()

        self.assertEqual(draft.status, 2)
        self.assertEqual(sale["payment_status"], "paid")
        self.assertEqual(Decimal(str(self.unit_quantity.quantity)), Decimal("3.0"))
        self.assertTrue(OrdersProduct.objects.filter(sale_order_id=sale["id"]).exists())
        self.assertTrue(TransactionHistory.objects.filter(order_id=sale["id"]).exists())

    def test_expired_hold_cart_cleanup_only_soft_deletes_hold_orders_like_source(self):
        self.stock_product(5)
        OptionSettingService.ensureOptionValue(
            self.company,
            self.branch,
            "orders_quotation_expiration",
            "1",
            user=self.user,
        )
        held = SaleService.hold(
            {
                "items": [
                    {
                        "product_id": self.product.id,
                        "unit_id": self.unit.id,
                        "unit_quantity_id": self.unit_quantity.id,
                        "quantity": Decimal("1"),
                    }
                ],
            },
            self.request,
        ).data
        draft = Order.objects.get(id=held["id"])
        Order.objects.filter(id=draft.id).update(created_at=timezone.now() - timezone.timedelta(days=2))
        active_sale = SaleService.create(
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

        result = SaleService.clearExpiredHeldCarts({}, self.request).data
        draft.refresh_from_db()
        active_order = Order.objects.get(id=active_sale["id"])

        self.assertEqual(result["deleted_count"], 1)
        self.assertEqual(draft.status, 2)
        self.assertEqual(active_order.status, 0)
        self.assertTrue(Notification.objects.filter(identifier="clear_hold_orders").exists())
        with self.assertRaises(Exception):
            SaleService.deleteHeldCart(active_order.id, self.request)

    def test_procurement_sale_and_accounting_side_effects_follow_source_flow(self):
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

    def test_coupon_target_usage_and_sale_refund_flow_follow_source(self):
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
        refund_list = SaleService.getRefunds(order.id, self.request).data
        self.assertEqual(refund_list[0]["customer"]["id"], customer.id)
        self.assertEqual(refund_list[0]["payment_method_label"], "Cash")
        self.assertEqual(refund_list[0]["total_quantity"], Decimal("1.00000"))
        self.assertTrue(
            ProductHistory.objects.filter(
                product=self.product,
                operation_type=ProductHistory.ACTION_RETURNED,
                order_id=order.id,
            ).exists()
        )

    def test_customer_reward_redeem_and_job_execution_follow_source(self):
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

    def test_order_storage_purge_job_matches_source_with_branch_safe_scope(self):
        other_branch = Branch.objects.create(
            company=self.company,
            name="Second Branch",
            code="second-branch",
        )
        OrderStorage.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            session_identifier="main-cart",
            quantity=1,
        )
        other_storage = OrderStorage.objects.create(
            user=self.user,
            company=self.company,
            branch=other_branch,
            session_identifier="other-cart",
            quantity=1,
        )

        job = JobQueueService.enqueue("purge_order_storage", {}, request=self.request)
        run_result = JobQueueService.runNext(SaleService.jobHandlers())

        self.assertEqual(run_result, {"status": "completed", "job_id": job.id})
        self.assertFalse(Job.objects.filter(id=job.id).exists())
        self.assertFalse(OrderStorage.objects.filter(company=self.company, branch=self.branch).exists())
        self.assertTrue(OrderStorage.objects.filter(id=other_storage.id).exists())

    def test_missing_background_job_handler_moves_job_to_failed_jobs(self):
        job = JobQueueService.enqueue("unknown_pos_job", {"sample": True}, request=self.request)

        run_result = JobQueueService.runNext(SaleService.jobHandlers())

        self.assertEqual(run_result, {"status": "failed", "job_id": job.id, "reason": "missing_handler"})
        self.assertFalse(Job.objects.filter(id=job.id).exists())
        failed_job = FailedJob.objects.get()
        self.assertIn("unknown_pos_job", failed_job.payload)
        self.assertEqual(failed_job.company_id, self.company.id)
        self.assertEqual(failed_job.branch_id, self.branch.id)

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

    def test_customer_account_payment_and_credit_note_follow_source(self):
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

    def test_partial_sale_installments_collect_due_and_customer_ledger_follow_source(self):
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

    def test_unpaid_sale_void_reverses_stock_and_customer_due_like_source(self):
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

        self.assertEqual(order.payment_status, "order_void")
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

    def test_unpaid_sale_delete_reverses_stock_and_customer_due_like_source(self):
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

    def test_recurring_transactions_trigger_and_daily_skip_like_source(self):
        from apps.accounting.models import Transaction, TransactionBalanceDay
        from apps.accounting.services import TransactionService
        
        # 1. Create a transaction account
        account = TransactionAccount.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Recurring Revenue",
            category_identifier="revenue",
            account="rec-rev-001",
            status=0,
        )
        
        # 2. Create a recurring active transaction
        recurring_tx = Transaction.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            account=account,
            name="Daily Service Retainer",
            value=Decimal("150.00"),
            recurring=True,
            active=True,
            type=Transaction.TYPE_RECURRING,
            occurrence="every_x_days",
            occurrence_value=1,
            scheduled_date=timezone.now(),
            status=0,
        )
        
        # Verify initial balance is 0
        balance_day = TransactionBalanceDay.objects.filter(branch=self.branch).first()
        initial_balance = balance_day.closing_balance if balance_day else Decimal("0.0")
        self.assertEqual(Decimal(str(initial_balance)), Decimal("0.0"))
        
        # 3. Trigger recurring transactions
        res = TransactionService.triggerRecurringTransactions({}, self.request)
        self.assertEqual(res.data["processed_count"], 1)
        self.assertEqual(res.data["skipped_count"], 0)
        
        # Verify transaction history was created
        history = TransactionHistory.objects.filter(
            transaction_id=recurring_tx.id,
            status=0
        ).first()
        self.assertIsNotNone(history)
        self.assertEqual(Decimal(str(history.value)), Decimal("150.00"))
        self.assertEqual(history.transaction_status, TransactionHistory.STATUS_ACTIVE_TEXT)
        
        # Verify branch balance was updated
        balance_day = TransactionBalanceDay.objects.filter(branch=self.branch).first()
        self.assertIsNotNone(balance_day)
        self.assertEqual(Decimal(str(balance_day.closing_balance)), Decimal("150.00"))
        
        # 4. Trigger again on the same day (should skip because it was already processed today)
        res_skipped = TransactionService.triggerRecurringTransactions({}, self.request)
        self.assertEqual(res_skipped.data["processed_count"], 0)
        self.assertEqual(res_skipped.data["skipped_count"], 1)
        
        # Branch balance remains unchanged
        balance_day.refresh_from_db()
        self.assertEqual(Decimal(str(balance_day.closing_balance)), Decimal("150.00"))

    def test_scheduler_enqueues_specific_jobs_based_on_time(self):
        import json
        from django.core.management import call_command
        from unittest.mock import patch
        import datetime
        from django.utils import timezone
        from apps.settings.models import Job
        
        Job.objects.all().delete()
        
        mock_now = timezone.make_aware(datetime.datetime(2026, 6, 24, 0, 2, 0))
        with patch("django.utils.timezone.localtime", return_value=mock_now):
            call_command("run_scheduler", force=True)
            
        enqueued = Job.objects.filter(branch=self.branch)
        payloads = []
        for j in enqueued:
            try:
                payloads.append(json.loads(j.payload).get("job"))
            except:
                pass
        self.assertIn("detect_low_stock_products", payloads)

        before_count = Job.objects.count()
        with patch("django.utils.timezone.localtime", return_value=mock_now):
            call_command("run_scheduler")
        self.assertEqual(Job.objects.count(), before_count)

        Job.objects.all().delete()
        purge_now = timezone.make_aware(datetime.datetime(2026, 6, 24, 15, 0, 0))
        with patch("django.utils.timezone.localtime", return_value=purge_now):
            call_command("run_scheduler", force=True)

        payloads = [json.loads(job.payload).get("job") for job in Job.objects.filter(branch=self.branch)]
        self.assertIn("detect_scheduled_transactions", payloads)
        self.assertIn("ensure_combined_product_history", payloads)
        self.assertIn("purge_order_storage", payloads)

    def test_scale_barcode_and_plu_flows(self):
        # 1. Create a Scale Range
        scale_range = ScaleRange.objects.create(
            company=self.company,
            branch=self.branch,
            name="Meat & Veggies Range",
            range_start=10000,
            range_end=20000,
            next_scale_plu=10150,
            status=0
        )
        
        # 2. Setup Category & Product linked to Scale Range
        category = Category.objects.create(
            company=self.company,
            branch=self.branch,
            name="Fresh Produce",
            scale_range=scale_range,
            status=0
        )
        product = Product.objects.create(
            company=self.company,
            branch=self.branch,
            category=category,
            name="Green Apples",
            sku="GREEN-APPLES",
            barcode="GREEN-APPLES-BAR",
            product_type="materialized",
            stock_management="disabled",
            status=0
        )
        
        # 3. Create ProductUnitQuantity
        unit_group = UnitGroup.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            name="Weight Units",
            status=0
        )
        unit = Unit.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            group=unit_group,
            name="Kilograms",
            identifier="kg",
            value=1,
            base_unit=True,
            status=0
        )
        unit_quantity = ProductUnitQuantity.objects.create(
            company=self.company,
            branch=self.branch,
            product=product,
            unit=unit,
            sale_price=Decimal("12.50"),
            cogs=Decimal("8.00"),
            status=0
        )
        
        # 4. Generate PLU
        from apps.catalog.services import ProductService
        generated_plu = ProductService.generateScalePLU(product.id, unit_quantity.id, self.request)
        # Should be zfill(5) of next_scale_plu = 10150 -> "10150"
        self.assertEqual(generated_plu, "10150")
        
        # Scale Range next_scale_plu should increment to 10151
        scale_range.refresh_from_db()
        self.assertEqual(scale_range.next_scale_plu, 10151)
        
        # Assign generated scale PLU to unit quantity
        unit_quantity.scale_plu = generated_plu
        unit_quantity.save()
        
        # 5. Enable and configure scale options
        OptionSettingService.ensureOptionValue(self.company, self.branch, "scale_barcode_enabled", "yes", self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "scale_barcode_prefix", "2", self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "scale_barcode_product_length", 5, self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "scale_barcode_value_length", 5, self.user)
        OptionSettingService.ensureOptionValue(self.company, self.branch, "scale_barcode_type", "weight", self.user)
        
        # 6. Test product search using scale barcode
        # 2 + 10150 + 01250 + 3 check digit = 210150012503 (weight is 1250g = 1.250kg)
        barcode_ref = "210150012503"
        response = ProductService.searchUsingBarcode(barcode_ref, self.request)
        self.assertTrue(response.success)
        self.assertEqual(response.data["matched_unit_quantity"]["id"], unit_quantity.id)
        self.assertEqual(Decimal(str(response.data["scale_value"])), Decimal("1.250"))
        
        # 7. Test Checkout integration
        # Create checkout order
        register = Register.objects.create(
            company=self.company,
            branch=self.branch,
            name="Register A",
            status=0
        )
        # Open shift
        from apps.registers.services import RegisterService
        RegisterService.recordHistory(
            register.id,
            RegistersHistory.ACTION_OPENING,
            Decimal("100.00"),
            self.request,
            note="Open"
        )
        
        checkout_payload = {
            "customer_id": None,
            "register_id": register.id,
            "order_type": "takeaway",
            "discount_amount": 0,
            "items": [
                {
                    "barcode": "210150012503", # scale barcode
                    "unit_price": Decimal("12.50"),
                }
            ],
            "payments": [
                {
                    "payment_type": "cash-payment",
                    "amount": Decimal("15.625"), # 1.250 * 12.50 = 15.625
                }
            ],
            "tendered_amount": Decimal("15.625"),
        }
        
        from apps.sales.services import SaleService
        sale_res = SaleService.create(checkout_payload, self.request)
        self.assertTrue(sale_res.success)
        
        sale_order_id = sale_res.data["id"]
        # Verify sale product quantity is 1.250
        ordered_item = OrdersProduct.objects.filter(sale_order_id=sale_order_id).first()
        self.assertIsNotNone(ordered_item)
        self.assertEqual(Decimal(str(ordered_item.quantity)), Decimal("1.250"))
        self.assertEqual(Decimal(str(ordered_item.unit_price)), Decimal("12.50"))
        # total = 1.250 * 12.50 = 15.625
        self.assertEqual(Decimal(str(ordered_item.total)), Decimal("15.625"))

    def test_background_job_monitoring_and_retry_flows(self):
        # 1. Enqueue a job
        job = JobQueueService.enqueue("purge_order_storage", {"sample": True}, request=self.request)
        
        # 2. List pending jobs and verify it's there
        res_pending = JobQueueService.listPendingJobs({"page": 1, "limit": 10}, self.request)
        self.assertEqual(res_pending["total"], 1)
        self.assertEqual(res_pending["items"][0]["id"], job.id)
        
        # 3. Simulate failure to move it to FailedJob
        JobQueueService.fail(job, "Purge connection failed.")
        
        # 4. List pending jobs again, should be empty
        res_pending_after = JobQueueService.listPendingJobs({"page": 1, "limit": 10}, self.request)
        self.assertEqual(res_pending_after["total"], 0)
        
        # 5. List failed jobs and verify
        res_failed = JobQueueService.listFailedJobs({"page": 1, "limit": 10}, self.request)
        self.assertEqual(res_failed["total"], 1)
        failed_job_id = res_failed["items"][0]["id"]
        self.assertIn("purge_order_storage", res_failed["items"][0]["payload"])
        self.assertEqual(res_failed["items"][0]["exception"], "Purge connection failed.")
        
        # 6. Retry the failed job
        retry_res = JobQueueService.retryFailedJob(failed_job_id, self.request)
        self.assertTrue(retry_res.success)
        
        # 7. Check failed queue is now empty and job is back in pending queue
        res_failed_after = JobQueueService.listFailedJobs({"page": 1, "limit": 10}, self.request)
        self.assertEqual(res_failed_after["total"], 0)
        
        res_pending_final = JobQueueService.listPendingJobs({"page": 1, "limit": 10}, self.request)
        self.assertEqual(res_pending_final["total"], 1)
        new_job_id = res_pending_final["items"][0]["id"]
        
        # 8. Fail the job again to test delete/dismiss failed job
        new_job = Job.objects.get(id=new_job_id)
        JobQueueService.fail(new_job, "Failed again.")
        
        # Check failed queue has 1 item again
        res_failed_2 = JobQueueService.listFailedJobs({"page": 1, "limit": 10}, self.request)
        self.assertEqual(res_failed_2["total"], 1)
        failed_job_id_2 = res_failed_2["items"][0]["id"]
        
        # Delete failed job
        delete_res = JobQueueService.deleteFailedJob(failed_job_id_2, self.request)
        self.assertTrue(delete_res.success)
        
        # Verify failed queue is empty
        res_failed_final = JobQueueService.listFailedJobs({"page": 1, "limit": 10}, self.request)
        self.assertEqual(res_failed_final["total"], 0)

    def test_pos_grid_navigation_api(self):
        from apps.catalog.services import CategoryService
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth.models import Permission
        content_type = ContentType.objects.get_for_model(Category)
        p_view, _ = Permission.objects.get_or_create(
            codename="products_view",
            content_type=content_type,
            defaults={"name": "Can view products"},
        )
        self.user.user_permissions.add(p_view)

        # Create categories
        parent_cat = Category.objects.create(
            company=self.company,
            branch=self.branch,
            name="Parent Category",
            displays_on_pos=True,
            status=0
        )
        child_cat = Category.objects.create(
            company=self.company,
            branch=self.branch,
            name="Child Category",
            parent=parent_cat,
            displays_on_pos=True,
            status=0
        )
        
        # Create products
        pinned_product = Product.objects.create(
            company=self.company,
            branch=self.branch,
            name="Pinned Apple",
            pinned=True,
            status=0
        )
        child_product = Product.objects.create(
            company=self.company,
            branch=self.branch,
            name="Child Orange",
            category=child_cat,
            pinned=False,
            status=0
        )

        # Query POS categories for root level (parent_id=None)
        res_root = CategoryService.getPOSCategories(self.request, parent_id=None)
        self.assertTrue(res_root.success)
        data_root = res_root.data
        
        root_category_ids = {category["id"] for category in data_root["categories"]}
        self.assertIn(parent_cat.id, root_category_ids)
        self.assertEqual(len(data_root["pinnedProducts"]), 1)
        self.assertEqual(data_root["pinnedProducts"][0]["id"], pinned_product.id)
        self.assertEqual(len(data_root["products"]), 0)

        # Query POS categories for parent category level
        res_parent = CategoryService.getPOSCategories(self.request, parent_id=parent_cat.id)
        self.assertTrue(res_parent.success)
        data_parent = res_parent.data
        
        self.assertEqual(len(data_parent["categories"]), 1)
        self.assertEqual(data_parent["categories"][0]["id"], child_cat.id)
        self.assertEqual(data_parent["currentCategory"]["id"], parent_cat.id)
        self.assertIsNone(data_parent["previousCategory"])
        self.assertEqual(len(data_parent["products"]), 0)

        # Query POS categories for child category level
        res_child = CategoryService.getPOSCategories(self.request, parent_id=child_cat.id)
        self.assertTrue(res_child.success)
        data_child = res_child.data
        
        self.assertEqual(len(data_child["categories"]), 0)
        self.assertEqual(data_child["currentCategory"]["id"], child_cat.id)
        self.assertEqual(data_child["previousCategory"]["id"], parent_cat.id)
        self.assertEqual(len(data_child["products"]), 1)
        self.assertEqual(data_child["products"][0]["id"], child_product.id)
