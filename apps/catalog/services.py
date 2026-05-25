from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Brand, Category, Product, Tax, TaxGroup, Unit, UnitGroup
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import serializeModelInstance


class CatalogService:
    @staticmethod
    def _tenant_queryset(model, user):
        return model.objects.filter(
            company_id=user.company_id,
            branch_id=user.branch_id,
        ).exclude(status=2)

    @staticmethod
    def _serialize_category(category):
        data = serializeModelInstance(category)
        data["parent_name"] = category.parent.name if category.parent else None
        return data

    @staticmethod
    def _serialize_brand(brand):
        return serializeModelInstance(brand)

    @staticmethod
    def _serialize_unit_group(unit_group):
        data = serializeModelInstance(unit_group)
        data["units_count"] = unit_group.units.exclude(status=2).count()
        return data

    @staticmethod
    def _serialize_unit(unit):
        data = serializeModelInstance(unit)
        data["unit_group_name"] = unit.unit_group.name if unit.unit_group else None
        return data

    @staticmethod
    def _serialize_tax_group(tax_group):
        data = serializeModelInstance(tax_group)
        data["taxes_count"] = tax_group.taxes.exclude(status=2).count()
        return data

    @staticmethod
    def _serialize_tax(tax):
        data = serializeModelInstance(tax)
        data["tax_group_name"] = tax.tax_group.name if tax.tax_group else None
        return data

    @staticmethod
    def _serialize_product(product):
        data = serializeModelInstance(product)
        data["category_name"] = product.category.name if product.category else None
        data["brand_name"] = product.brand.name if product.brand else None
        data["tax_group_name"] = product.tax_group.name if product.tax_group else None
        data["unit_group_name"] = product.unit_group.name if product.unit_group else None
        data["variants_count"] = product.variants.exclude(status=2).count()
        return data

    @staticmethod
    def _get_tenant_object(model, user, object_id, label):
        instance = CatalogService._tenant_queryset(model, user).filter(id=object_id).first()
        if instance is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, f"{label} not found.")
        return instance

    @staticmethod
    def _unique_value(model, user, field_name, raw_value, exclude_id=None):
        candidate = raw_value
        counter = 1

        while True:
            qs = CatalogService._tenant_queryset(model, user).filter(**{field_name: candidate})
            if exclude_id is not None:
                qs = qs.exclude(id=exclude_id)
            if not qs.exists():
                return candidate
            counter += 1
            candidate = f"{raw_value}-{counter}"

    @staticmethod
    def _build_code(model, user, name, provided=None, exclude_id=None):
        base = slugify(provided or name or "item") or "item"
        return CatalogService._unique_value(model, user, "code", base, exclude_id=exclude_id)

    @staticmethod
    def _build_slug(model, user, name, provided=None, exclude_id=None):
        base = slugify(provided or name or "product") or "product"
        return CatalogService._unique_value(model, user, "slug", base, exclude_id=exclude_id)

    @staticmethod
    def _ensure_related(model, user, object_id, label):
        if object_id is None:
            return None
        return CatalogService._get_tenant_object(model, user, object_id, label)

    @staticmethod
    def listCategories(user):
        categories = CatalogService._tenant_queryset(Category, user).select_related("parent").order_by("name")
        return [CatalogService._serialize_category(item) for item in categories]

    @staticmethod
    def createCategory(user, payload):
        parent = CatalogService._ensure_related(Category, user, payload.parent_id, "Parent category")
        category = Category.objects.create(
            company_id=user.company_id,
            branch_id=user.branch_id,
            name=payload.name,
            code=CatalogService._build_code(Category, user, payload.name, payload.code),
            parent=parent,
            description=payload.description or "",
        )
        return CatalogService._serialize_category(category)

    @staticmethod
    def updateCategory(user, category_id, payload):
        category = CatalogService._get_tenant_object(Category, user, category_id, "Category")
        if payload.name is not None:
            category.name = payload.name
        if payload.code is not None or payload.name is not None:
            category.code = CatalogService._build_code(
                Category,
                user,
                payload.name or category.name,
                payload.code or category.code,
                exclude_id=category.id,
            )
        if payload.parent_id is not None:
            category.parent = CatalogService._ensure_related(Category, user, payload.parent_id, "Parent category")
        if payload.description is not None:
            category.description = payload.description
        if payload.status is not None:
            category.status = payload.status
        category.save()
        return CatalogService._serialize_category(category)

    @staticmethod
    def deleteCategory(user, category_id):
        category = CatalogService._get_tenant_object(Category, user, category_id, "Category")
        category.soft_delete()
        return {"id": category_id}

    @staticmethod
    def listBrands(user):
        brands = CatalogService._tenant_queryset(Brand, user).order_by("name")
        return [CatalogService._serialize_brand(item) for item in brands]

    @staticmethod
    def createBrand(user, payload):
        brand = Brand.objects.create(
            company_id=user.company_id,
            branch_id=user.branch_id,
            name=payload.name,
            code=CatalogService._build_code(Brand, user, payload.name, payload.code),
            description=payload.description or "",
        )
        return CatalogService._serialize_brand(brand)

    @staticmethod
    def updateBrand(user, brand_id, payload):
        brand = CatalogService._get_tenant_object(Brand, user, brand_id, "Brand")
        if payload.name is not None:
            brand.name = payload.name
        if payload.code is not None or payload.name is not None:
            brand.code = CatalogService._build_code(
                Brand,
                user,
                payload.name or brand.name,
                payload.code or brand.code,
                exclude_id=brand.id,
            )
        if payload.description is not None:
            brand.description = payload.description
        if payload.status is not None:
            brand.status = payload.status
        brand.save()
        return CatalogService._serialize_brand(brand)

    @staticmethod
    def deleteBrand(user, brand_id):
        brand = CatalogService._get_tenant_object(Brand, user, brand_id, "Brand")
        brand.soft_delete()
        return {"id": brand_id}

    @staticmethod
    def listUnitGroups(user):
        unit_groups = CatalogService._tenant_queryset(UnitGroup, user).prefetch_related("units").order_by("name")
        return [CatalogService._serialize_unit_group(item) for item in unit_groups]

    @staticmethod
    def createUnitGroup(user, payload):
        unit_group = UnitGroup.objects.create(
            company_id=user.company_id,
            branch_id=user.branch_id,
            name=payload.name,
            code=CatalogService._build_code(UnitGroup, user, payload.name, payload.code),
            description=payload.description or "",
        )
        return CatalogService._serialize_unit_group(unit_group)

    @staticmethod
    def updateUnitGroup(user, unit_group_id, payload):
        unit_group = CatalogService._get_tenant_object(UnitGroup, user, unit_group_id, "Unit group")
        if payload.name is not None:
            unit_group.name = payload.name
        if payload.code is not None or payload.name is not None:
            unit_group.code = CatalogService._build_code(
                UnitGroup,
                user,
                payload.name or unit_group.name,
                payload.code or unit_group.code,
                exclude_id=unit_group.id,
            )
        if payload.description is not None:
            unit_group.description = payload.description
        if payload.status is not None:
            unit_group.status = payload.status
        unit_group.save()
        return CatalogService._serialize_unit_group(unit_group)

    @staticmethod
    def deleteUnitGroup(user, unit_group_id):
        unit_group = CatalogService._get_tenant_object(UnitGroup, user, unit_group_id, "Unit group")
        unit_group.soft_delete()
        return {"id": unit_group_id}

    @staticmethod
    def listUnits(user):
        units = CatalogService._tenant_queryset(Unit, user).select_related("unit_group").order_by("unit_group__name", "name")
        return [CatalogService._serialize_unit(item) for item in units]

    @staticmethod
    @transaction.atomic
    def createUnit(user, payload):
        unit_group = CatalogService._ensure_related(UnitGroup, user, payload.unit_group_id, "Unit group")
        if payload.is_base_unit:
            Unit.objects.filter(unit_group=unit_group).update(is_base_unit=False)
        unit = Unit.objects.create(
            company_id=user.company_id,
            branch_id=user.branch_id,
            unit_group=unit_group,
            name=payload.name,
            short_name=payload.short_name,
            factor=payload.factor,
            is_base_unit=payload.is_base_unit,
        )
        return CatalogService._serialize_unit(unit)

    @staticmethod
    @transaction.atomic
    def updateUnit(user, unit_id, payload):
        unit = CatalogService._get_tenant_object(Unit, user, unit_id, "Unit")
        if payload.unit_group_id is not None:
            unit.unit_group = CatalogService._ensure_related(UnitGroup, user, payload.unit_group_id, "Unit group")
        if payload.name is not None:
            unit.name = payload.name
        if payload.short_name is not None:
            unit.short_name = payload.short_name
        if payload.factor is not None:
            unit.factor = payload.factor
        if payload.is_base_unit is not None:
            unit.is_base_unit = payload.is_base_unit
            if payload.is_base_unit:
                Unit.objects.filter(unit_group=unit.unit_group).exclude(id=unit.id).update(is_base_unit=False)
        if payload.status is not None:
            unit.status = payload.status
        unit.save()
        return CatalogService._serialize_unit(unit)

    @staticmethod
    def deleteUnit(user, unit_id):
        unit = CatalogService._get_tenant_object(Unit, user, unit_id, "Unit")
        unit.soft_delete()
        return {"id": unit_id}

    @staticmethod
    def listTaxGroups(user):
        tax_groups = CatalogService._tenant_queryset(TaxGroup, user).prefetch_related("taxes").order_by("name")
        return [CatalogService._serialize_tax_group(item) for item in tax_groups]

    @staticmethod
    def createTaxGroup(user, payload):
        tax_group = TaxGroup.objects.create(
            company_id=user.company_id,
            branch_id=user.branch_id,
            name=payload.name,
            code=CatalogService._build_code(TaxGroup, user, payload.name, payload.code),
            description=payload.description or "",
        )
        return CatalogService._serialize_tax_group(tax_group)

    @staticmethod
    def updateTaxGroup(user, tax_group_id, payload):
        tax_group = CatalogService._get_tenant_object(TaxGroup, user, tax_group_id, "Tax group")
        if payload.name is not None:
            tax_group.name = payload.name
        if payload.code is not None or payload.name is not None:
            tax_group.code = CatalogService._build_code(
                TaxGroup,
                user,
                payload.name or tax_group.name,
                payload.code or tax_group.code,
                exclude_id=tax_group.id,
            )
        if payload.description is not None:
            tax_group.description = payload.description
        if payload.status is not None:
            tax_group.status = payload.status
        tax_group.save()
        return CatalogService._serialize_tax_group(tax_group)

    @staticmethod
    def deleteTaxGroup(user, tax_group_id):
        tax_group = CatalogService._get_tenant_object(TaxGroup, user, tax_group_id, "Tax group")
        tax_group.soft_delete()
        return {"id": tax_group_id}

    @staticmethod
    def listTaxes(user):
        taxes = CatalogService._tenant_queryset(Tax, user).select_related("tax_group").order_by("tax_group__name", "name")
        return [CatalogService._serialize_tax(item) for item in taxes]

    @staticmethod
    def createTax(user, payload):
        tax_group = CatalogService._ensure_related(TaxGroup, user, payload.tax_group_id, "Tax group")
        tax = Tax.objects.create(
            company_id=user.company_id,
            branch_id=user.branch_id,
            tax_group=tax_group,
            name=payload.name,
            rate=payload.rate,
            is_inclusive=payload.is_inclusive,
        )
        return CatalogService._serialize_tax(tax)

    @staticmethod
    def updateTax(user, tax_id, payload):
        tax = CatalogService._get_tenant_object(Tax, user, tax_id, "Tax")
        if payload.tax_group_id is not None:
            tax.tax_group = CatalogService._ensure_related(TaxGroup, user, payload.tax_group_id, "Tax group")
        if payload.name is not None:
            tax.name = payload.name
        if payload.rate is not None:
            tax.rate = payload.rate
        if payload.is_inclusive is not None:
            tax.is_inclusive = payload.is_inclusive
        if payload.status is not None:
            tax.status = payload.status
        tax.save()
        return CatalogService._serialize_tax(tax)

    @staticmethod
    def deleteTax(user, tax_id):
        tax = CatalogService._get_tenant_object(Tax, user, tax_id, "Tax")
        tax.soft_delete()
        return {"id": tax_id}

    @staticmethod
    def listProducts(user):
        products = (
            CatalogService._tenant_queryset(Product, user)
            .select_related("category", "brand", "tax_group", "unit_group")
            .prefetch_related("variants")
            .order_by("name")
        )
        return [CatalogService._serialize_product(item) for item in products]

    @staticmethod
    def createProduct(user, payload):
        category = CatalogService._ensure_related(Category, user, payload.category_id, "Category")
        brand = CatalogService._ensure_related(Brand, user, payload.brand_id, "Brand")
        tax_group = CatalogService._ensure_related(TaxGroup, user, payload.tax_group_id, "Tax group")
        unit_group = CatalogService._ensure_related(UnitGroup, user, payload.unit_group_id, "Unit group")
        product = Product.objects.create(
            company_id=user.company_id,
            branch_id=user.branch_id,
            category=category,
            brand=brand,
            tax_group=tax_group,
            unit_group=unit_group,
            name=payload.name,
            slug=CatalogService._build_slug(Product, user, payload.name, payload.slug),
            sku=payload.sku,
            product_type=payload.product_type,
            description=payload.description or "",
            purchase_price=payload.purchase_price,
            selling_price=payload.selling_price,
            mrp=payload.mrp,
            min_stock=payload.min_stock,
            track_stock=payload.track_stock,
            allow_decimal_qty=payload.allow_decimal_qty,
        )
        return CatalogService._serialize_product(product)

    @staticmethod
    def updateProduct(user, product_id, payload):
        product = CatalogService._get_tenant_object(Product, user, product_id, "Product")
        if payload.category_id is not None:
            product.category = CatalogService._ensure_related(Category, user, payload.category_id, "Category")
        if payload.brand_id is not None:
            product.brand = CatalogService._ensure_related(Brand, user, payload.brand_id, "Brand")
        if payload.tax_group_id is not None:
            product.tax_group = CatalogService._ensure_related(TaxGroup, user, payload.tax_group_id, "Tax group")
        if payload.unit_group_id is not None:
            product.unit_group = CatalogService._ensure_related(UnitGroup, user, payload.unit_group_id, "Unit group")
        if payload.name is not None:
            product.name = payload.name
        if payload.slug is not None or payload.name is not None:
            product.slug = CatalogService._build_slug(
                Product,
                user,
                payload.name or product.name,
                payload.slug or product.slug,
                exclude_id=product.id,
            )
        if payload.sku is not None:
            product.sku = payload.sku
        if payload.product_type is not None:
            product.product_type = payload.product_type
        if payload.description is not None:
            product.description = payload.description
        if payload.purchase_price is not None:
            product.purchase_price = payload.purchase_price
        if payload.selling_price is not None:
            product.selling_price = payload.selling_price
        if payload.mrp is not None:
            product.mrp = payload.mrp
        if payload.min_stock is not None:
            product.min_stock = payload.min_stock
        if payload.track_stock is not None:
            product.track_stock = payload.track_stock
        if payload.allow_decimal_qty is not None:
            product.allow_decimal_qty = payload.allow_decimal_qty
        if payload.status is not None:
            product.status = payload.status
        product.save()
        return CatalogService._serialize_product(product)

    @staticmethod
    def deleteProduct(user, product_id):
        product = CatalogService._get_tenant_object(Product, user, product_id, "Product")
        product.soft_delete()
        return {"id": product_id}
