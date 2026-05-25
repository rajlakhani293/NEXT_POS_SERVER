from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.catalog.controllers import CatalogController
from apps.catalog.schemas import (
    BrandIn,
    BrandUpdateIn,
    CategoryIn,
    CategoryUpdateIn,
    ProductIn,
    ProductUpdateIn,
    TaxGroupIn,
    TaxGroupUpdateIn,
    TaxIn,
    TaxUpdateIn,
    UnitGroupIn,
    UnitGroupUpdateIn,
    UnitIn,
    UnitUpdateIn,
)
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse


router = Router(tags=["catalog"])


@router.get("/categories", auth=auth_bearer, response=ApiResponse)
@permission_required("products_view")
def listCategories(request):
    return CatalogController.listCategories(request)


@router.post("/categories", auth=auth_bearer, response=ApiResponse)
@permission_required("products_create")
def createCategory(request, payload: CategoryIn):
    return CatalogController.createCategory(request, payload)


@router.put("/categories/{category_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_update")
def updateCategory(request, category_id: int, payload: CategoryUpdateIn):
    return CatalogController.updateCategory(request, category_id, payload)


@router.delete("/categories/{category_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_delete")
def deleteCategory(request, category_id: int):
    return CatalogController.deleteCategory(request, category_id)


@router.get("/brands", auth=auth_bearer, response=ApiResponse)
@permission_required("products_view")
def listBrands(request):
    return CatalogController.listBrands(request)


@router.post("/brands", auth=auth_bearer, response=ApiResponse)
@permission_required("products_create")
def createBrand(request, payload: BrandIn):
    return CatalogController.createBrand(request, payload)


@router.put("/brands/{brand_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_update")
def updateBrand(request, brand_id: int, payload: BrandUpdateIn):
    return CatalogController.updateBrand(request, brand_id, payload)


@router.delete("/brands/{brand_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_delete")
def deleteBrand(request, brand_id: int):
    return CatalogController.deleteBrand(request, brand_id)


@router.get("/unit-groups", auth=auth_bearer, response=ApiResponse)
@permission_required("products_view")
def listUnitGroups(request):
    return CatalogController.listUnitGroups(request)


@router.post("/unit-groups", auth=auth_bearer, response=ApiResponse)
@permission_required("products_create")
def createUnitGroup(request, payload: UnitGroupIn):
    return CatalogController.createUnitGroup(request, payload)


@router.put("/unit-groups/{unit_group_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_update")
def updateUnitGroup(request, unit_group_id: int, payload: UnitGroupUpdateIn):
    return CatalogController.updateUnitGroup(request, unit_group_id, payload)


@router.delete("/unit-groups/{unit_group_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_delete")
def deleteUnitGroup(request, unit_group_id: int):
    return CatalogController.deleteUnitGroup(request, unit_group_id)


@router.get("/units", auth=auth_bearer, response=ApiResponse)
@permission_required("products_view")
def listUnits(request):
    return CatalogController.listUnits(request)


@router.post("/units", auth=auth_bearer, response=ApiResponse)
@permission_required("products_create")
def createUnit(request, payload: UnitIn):
    return CatalogController.createUnit(request, payload)


@router.put("/units/{unit_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_update")
def updateUnit(request, unit_id: int, payload: UnitUpdateIn):
    return CatalogController.updateUnit(request, unit_id, payload)


@router.delete("/units/{unit_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_delete")
def deleteUnit(request, unit_id: int):
    return CatalogController.deleteUnit(request, unit_id)


@router.get("/tax-groups", auth=auth_bearer, response=ApiResponse)
@permission_required("products_view")
def listTaxGroups(request):
    return CatalogController.listTaxGroups(request)


@router.post("/tax-groups", auth=auth_bearer, response=ApiResponse)
@permission_required("products_create")
def createTaxGroup(request, payload: TaxGroupIn):
    return CatalogController.createTaxGroup(request, payload)


@router.put("/tax-groups/{tax_group_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_update")
def updateTaxGroup(request, tax_group_id: int, payload: TaxGroupUpdateIn):
    return CatalogController.updateTaxGroup(request, tax_group_id, payload)


@router.delete("/tax-groups/{tax_group_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_delete")
def deleteTaxGroup(request, tax_group_id: int):
    return CatalogController.deleteTaxGroup(request, tax_group_id)


@router.get("/taxes", auth=auth_bearer, response=ApiResponse)
@permission_required("products_view")
def listTaxes(request):
    return CatalogController.listTaxes(request)


@router.post("/taxes", auth=auth_bearer, response=ApiResponse)
@permission_required("products_create")
def createTax(request, payload: TaxIn):
    return CatalogController.createTax(request, payload)


@router.put("/taxes/{tax_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_update")
def updateTax(request, tax_id: int, payload: TaxUpdateIn):
    return CatalogController.updateTax(request, tax_id, payload)


@router.delete("/taxes/{tax_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_delete")
def deleteTax(request, tax_id: int):
    return CatalogController.deleteTax(request, tax_id)


@router.get("/products", auth=auth_bearer, response=ApiResponse)
@permission_required("products_view")
def listProducts(request):
    return CatalogController.listProducts(request)


@router.post("/products", auth=auth_bearer, response=ApiResponse)
@permission_required("products_create")
def createProduct(request, payload: ProductIn):
    return CatalogController.createProduct(request, payload)


@router.put("/products/{product_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_update")
def updateProduct(request, product_id: int, payload: ProductUpdateIn):
    return CatalogController.updateProduct(request, product_id, payload)


@router.delete("/products/{product_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("products_delete")
def deleteProduct(request, product_id: int):
    return CatalogController.deleteProduct(request, product_id)
