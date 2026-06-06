# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class StockLot(TenantAwareModel):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="stock_lots")
    purchase_item = models.ForeignKey(
        "purchases.PurchaseItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_lots",
    )
    batch_number = models.CharField(max_length=120, blank=True)
    expiry_date = models.DateField(blank=True, null=True)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_available = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)


class StockLedger(TenantAwareModel):
    ENTRY_TYPES = [
        ("purchase", "Purchase"),
        ("sale", "Sale"),
        ("sale_return", "Sale Return"),
        ("adjustment_in", "Adjustment In"),
        ("adjustment_out", "Adjustment Out"),
        ("transfer_out", "Transfer Out"),
        ("transfer_in", "Transfer In"),
        ("opening_stock", "Opening Stock"),
    ]

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="stock_entries")
    lot = models.ForeignKey(StockLot, on_delete=models.SET_NULL, null=True, blank=True, related_name="ledger_entries")
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveBigIntegerField(blank=True, null=True)
    note = models.TextField(blank=True)


class StockAdjustment(TenantAwareModel):
    adjustment_type = models.CharField(max_length=20, choices=[("increase", "Increase"), ("decrease", "Decrease")])
    code = models.CharField(max_length=50)
    reason = models.CharField(max_length=255)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "code")]


class StockTransfer(TenantAwareModel):
    code = models.CharField(max_length=50)
    destination_branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.PROTECT,
        related_name="incoming_transfers",
    )
    transfer_status = models.CharField(
        max_length=20,
        choices=[("draft", "Draft"), ("sent", "Sent"), ("received", "Received"), ("cancelled", "Cancelled")],
        default="draft",
    )
    sent_at = models.DateTimeField(blank=True, null=True)
    received_at = models.DateTimeField(blank=True, null=True)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "code")]


class StockTransferItem(TenantAwareModel):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="transfer_items")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    received_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)


class LowStockAlert(TenantAwareModel):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="low_stock_alerts")
    threshold_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    last_notified_at = models.DateTimeField(blank=True, null=True)
