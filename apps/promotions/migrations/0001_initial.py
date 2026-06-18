from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('sales', '0001_initial'),
        ('catalog', '0001_initial'),
        ('organizations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Coupon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('status', models.IntegerField(choices=[(0, 'Active'), (1, 'Deactive'), (2, 'Delete')], default=0, help_text='0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.')),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_%(app_label)s_%(class)ss', to=settings.AUTH_USER_MODEL)),
                ('name', models.CharField(max_length=150)),
                ('code', models.CharField(max_length=120)),
                ('type', models.CharField(choices=[('flat_discount', 'Flat Discount'), ('percentage_discount', 'Percentage Discount')], max_length=30)),
                ('discount_value', models.DecimalField(decimal_places=2, max_digits=12)),
                ('minimum_cart_value', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('maximum_cart_value', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('valid_until', models.DateTimeField(blank=True, null=True)),
                ('valid_hours_start', models.TimeField(blank=True, null=True)),
                ('valid_hours_end', models.TimeField(blank=True, null=True)),
                ('limit_usage', models.PositiveIntegerField(default=0)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.branch')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.company')),
            ],
            options={
                'db_table': 'coupons',
                'ordering': ['name'],
                'unique_together': {('branch', 'code')},
            },
        ),
        migrations.CreateModel(
            name='AppliedCoupon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('status', models.IntegerField(choices=[(0, 'Active'), (1, 'Deactive'), (2, 'Delete')], default=0, help_text='0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.')),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_%(app_label)s_%(class)ss', to=settings.AUTH_USER_MODEL)),
                ('code', models.CharField(max_length=150)),
                ('name', models.CharField(blank=True, default='', max_length=150)),
                ('type', models.CharField(max_length=30)),
                ('discount_value', models.DecimalField(decimal_places=2, max_digits=12)),
                ('minimum_cart_value', models.DecimalField(decimal_places=5, default=0, max_digits=18)),
                ('maximum_cart_value', models.DecimalField(decimal_places=5, default=0, max_digits=18)),
                ('limit_usage', models.PositiveIntegerField(default=0)),
                ('discount_amount', models.DecimalField(db_column='value', decimal_places=2, default=0, max_digits=12)),
                ('counted', models.BooleanField(default=False)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.branch')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.company')),
                ('coupon', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='applied_orders', to='promotions.coupon')),
                ('customer_coupon_id', models.PositiveIntegerField(blank=True, null=True)),
                ('sale_order', models.ForeignKey(db_column='order_id', on_delete=django.db.models.deletion.CASCADE, related_name='applied_coupons', to='sales.saleorder')),
            ],
            options={
                'db_table': 'orders_coupons',
            },
        ),
        migrations.CreateModel(
            name='CouponProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('status', models.IntegerField(choices=[(0, 'Active'), (1, 'Deactive'), (2, 'Delete')], default=0, help_text='0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.')),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_%(app_label)s_%(class)ss', to=settings.AUTH_USER_MODEL)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.branch')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.company')),
                ('coupon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupon_products', to='promotions.coupon')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupon_links', to='catalog.product')),
            ],
            options={
                'db_table': 'coupons_products',
                'unique_together': {('coupon', 'product')},
            },
        ),
        migrations.CreateModel(
            name='CouponCustomerGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('status', models.IntegerField(choices=[(0, 'Active'), (1, 'Deactive'), (2, 'Delete')], default=0, help_text='0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.')),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_%(app_label)s_%(class)ss', to=settings.AUTH_USER_MODEL)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.branch')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.company')),
                ('coupon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupon_customer_groups', to='promotions.coupon')),
                ('customer_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupon_links', to='customers.customergroup')),
            ],
            options={
                'db_table': 'coupons_customers_groups',
                'unique_together': {('coupon', 'customer_group')},
            },
        ),
        migrations.CreateModel(
            name='CouponCustomer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('status', models.IntegerField(choices=[(0, 'Active'), (1, 'Deactive'), (2, 'Delete')], default=0, help_text='0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.')),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_%(app_label)s_%(class)ss', to=settings.AUTH_USER_MODEL)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.branch')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.company')),
                ('coupon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupon_customers', to='promotions.coupon')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupon_links', to='customers.customer')),
            ],
            options={
                'db_table': 'coupons_customers',
                'unique_together': {('coupon', 'customer')},
            },
        ),
        migrations.CreateModel(
            name='CouponCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('status', models.IntegerField(choices=[(0, 'Active'), (1, 'Deactive'), (2, 'Delete')], default=0, help_text='0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.')),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_%(app_label)s_%(class)ss', to=settings.AUTH_USER_MODEL)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.branch')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupon_links', to='catalog.category')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.company')),
                ('coupon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupon_categories', to='promotions.coupon')),
            ],
            options={
                'db_table': 'coupons_categories',
                'unique_together': {('coupon', 'category')},
            },
        ),
    ]
