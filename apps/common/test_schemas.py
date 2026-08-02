from django.db import IntegrityError
from django.test import SimpleTestCase
from pydantic import ValidationError

from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema
from apps.settings.schemas import NotificationIn
from apps.sales.schemas import SaleCreateIn
from config.api import parse_integrity_error


class SharedSchemaTests(SimpleTestCase):
    def test_bulk_ids_accepts_scalar_and_list(self):
        self.assertEqual(BulkIdsSchema(ids=1).ids, 1)
        self.assertEqual(BulkIdsSchema(ids=[1, 2]).ids, [1, 2])

    def test_status_update_only_accepts_active_or_inactive(self):
        self.assertEqual(StatusUpdateSchema(ids=1, status=0).status, 0)
        self.assertEqual(StatusUpdateSchema(ids=1, status=1).status, 1)
        with self.assertRaises(ValidationError):
            StatusUpdateSchema(ids=1, status=2)

    def test_integrity_duplicate_errors_return_field_specific_message(self):
        examples = [
            (
                "UNIQUE constraint failed: taxes.branch_id, taxes.name",
                "Tax name already exists.",
                "name",
            ),
            (
                "duplicate key value violates unique constraint products_branch_barcode_key DETAIL: Key (branch_id, barcode)=(1, 123) already exists.",
                "Product barcode already exists.",
                "barcode",
            ),
            (
                "(1062, \"Duplicate entry '1-piece' for key 'units_branch_id_identifier_c616fbc4'\")",
                "Unit identifier already exists.",
                "identifier",
            ),
        ]

        for raw_error, expected_message, expected_field in examples:
            message, data = parse_integrity_error(IntegrityError(raw_error))
            self.assertEqual(message, expected_message)
            self.assertEqual(data, {"field": expected_field})

    def test_mutable_defaults_are_isolated(self):
        first_sale = SaleCreateIn(items=[])
        second_sale = SaleCreateIn(items=[])
        first_sale.coupon_codes.append("WELCOME")
        self.assertEqual(second_sale.coupon_codes, [])

        first_notification = NotificationIn(title="One", actions={})
        second_notification = NotificationIn(title="Two", actions={})
        first_notification.actions["source"] = "test"
        self.assertEqual(second_notification.actions, {})
