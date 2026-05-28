# Generated manually for simplified branch-level products.

from django.db import migrations, models
import django.db.models.deletion


def move_product_branch_data(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    ProductBranch = apps.get_model("catalog", "ProductBranch")
    Branch = apps.get_model("organizations", "Branch")

    for product in Product.objects.all():
        product_branch = ProductBranch.objects.filter(product_id=product.id).order_by("id").first()
        branch = None
        if product_branch:
            branch = product_branch.branch
        if branch is None:
            branch = Branch.objects.filter(company_id=product.company_id).exclude(status=2).order_by("id").first()
        if branch is None:
            continue

        product.branch_id = branch.id
        if product_branch:
            product.purchase_price = product_branch.purchase_price
            product.selling_price = product_branch.selling_price
            product.mrp = product_branch.mrp
            product.wholesale_price = product_branch.wholesale_price
            product.current_stock = product_branch.current_stock
            product.opening_stock = product_branch.opening_stock
            product.min_stock = product_branch.min_stock
            product.max_stock = product_branch.max_stock
            product.reorder_level = product_branch.reorder_level
            product.stock_alert_enabled = product_branch.stock_alert_enabled
        product.save()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_alter_productvariant_unique_together_and_more"),
        ("organizations", "0002_alter_branch_status_alter_company_status"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="product",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="product",
            name="branch",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="%(class)ss",
                to="organizations.branch",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="purchase_price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="product",
            name="selling_price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="product",
            name="mrp",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="product",
            name="wholesale_price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="product",
            name="current_stock",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="product",
            name="opening_stock",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="product",
            name="min_stock",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="product",
            name="max_stock",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="product",
            name="reorder_level",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="product",
            name="stock_alert_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(move_product_branch_data, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="product",
            name="branch",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="%(class)ss",
                to="organizations.branch",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="product",
            unique_together={("branch", "sku"), ("branch", "barcode"), ("branch", "slug")},
        ),
        migrations.DeleteModel(
            name="ProductBranch",
        ),
    ]
