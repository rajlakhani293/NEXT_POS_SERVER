# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class StockLedger(TenantAwareModel):
    ENTRY_TYPES = [
        ("purchase", "Purchase"),
        ("sale", "Sale"),
        ("sale_return", "Sale Return"),
        ("adjustment_in", "Adjustment In"),
        ("adjustment_out", "Adjustment Out"),
        ("adjustment_set", "Adjustment Set"),
        ("transfer_out", "Transfer Out"),
        ("transfer_in", "Transfer In"),
        ("opening_stock", "Opening Stock"),
    ]

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="stock_entries")
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveBigIntegerField(blank=True, null=True)
    note = models.TextField(blank=True)


class StockAdjustment(TenantAwareModel):
    ADJUSTMENT_ACTIONS = [
        ("added", "Add"),
        ("deleted", "Delete"),
        ("defective", "Defective"),
        ("lost", "Lost"),
        ("set", "Set"),
    ]

    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_ACTIONS)
    code = models.CharField(max_length=50)
    reason = models.CharField(max_length=255)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "code")]
