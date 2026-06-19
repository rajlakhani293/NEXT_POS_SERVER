from django.test import SimpleTestCase
from pydantic import ValidationError

from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema
from apps.settings.schemas import NotificationIn
from apps.sales.schemas import SaleCreateIn


class SharedSchemaTests(SimpleTestCase):
    def test_bulk_ids_accepts_scalar_and_list(self):
        self.assertEqual(BulkIdsSchema(ids=1).ids, 1)
        self.assertEqual(BulkIdsSchema(ids=[1, 2]).ids, [1, 2])

    def test_status_update_only_accepts_active_or_inactive(self):
        self.assertEqual(StatusUpdateSchema(ids=1, status=0).status, 0)
        self.assertEqual(StatusUpdateSchema(ids=1, status=1).status, 1)
        with self.assertRaises(ValidationError):
            StatusUpdateSchema(ids=1, status=2)

    def test_mutable_defaults_are_isolated(self):
        first_sale = SaleCreateIn(items=[])
        second_sale = SaleCreateIn(items=[])
        first_sale.coupon_codes.append("WELCOME")
        self.assertEqual(second_sale.coupon_codes, [])

        first_notification = NotificationIn(title="One")
        second_notification = NotificationIn(title="Two")
        first_notification.payload["source"] = "test"
        self.assertEqual(second_notification.payload, {})
