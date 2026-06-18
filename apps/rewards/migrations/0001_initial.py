from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('organizations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('customers', '0003_customercoupon_customerreward_remove_customer_branch_and_more'),
        ('promotions', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RewardSystem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('status', models.IntegerField(choices=[(0, 'Active'), (1, 'Deactive'), (2, 'Delete')], default=0, help_text='0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.')),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_%(app_label)s_%(class)ss', to=settings.AUTH_USER_MODEL)),
                ('name', models.CharField(max_length=150)),
                ('target', models.PositiveIntegerField(default=0)),
                ('description', models.TextField(blank=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.branch')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.company')),
                ('coupon', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reward_systems', to='promotions.coupon')),
            ],
            options={
                'db_table': 'rewards_system',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='RewardsSystemRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('status', models.IntegerField(choices=[(0, 'Active'), (1, 'Deactive'), (2, 'Delete')], default=0, help_text='0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.')),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_%(app_label)s_%(class)ss', to=settings.AUTH_USER_MODEL)),
                ('from_amount', models.DecimalField(db_column='from', decimal_places=5, default=0, max_digits=18)),
                ('to_amount', models.DecimalField(db_column='to', decimal_places=5, default=0, max_digits=18)),
                ('reward', models.DecimalField(decimal_places=5, default=0, max_digits=18)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.branch')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to='organizations.company')),
                ('reward_system', models.ForeignKey(db_column='reward_id', on_delete=django.db.models.deletion.CASCADE, related_name='rules', to='rewards.rewardsystem')),
            ],
            options={
                'db_table': 'rewards_system_rules',
                'ordering': ['from_amount'],
            },
        ),
    ]
