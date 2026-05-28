from typing import Optional
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.catalog.schemas import (
    BrandIn,
    BrandUpdateIn,
    CategoryIn,
    CategoryUpdateIn,
    DeleteSchema,
    ProductIn,
    ProductUpdateIn,
    StatusUpdateSchema,
    TaxGroupIn,
    TaxGroupUpdateIn,
    TaxIn,
    TaxUpdateIn,
    UnitGroupIn,
    UnitGroupUpdateIn,
    UnitIn,
    UnitUpdateIn,
)
from apps.catalog.services import (
    BrandService,
    CategoryService,
    ProductService,
    TaxGroupService,
    TaxService,
    UnitGroupService,
    UnitService,
)
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse


router = Router(tags=["catalog"], auth=auth_bearer)


@router.post("/categories/", response=ApiResponse)
@permission_required("products_create")
def createCategory(request, payload: CategoryIn):
    return CategoryService.create(payload.dict(), request)


@router.post("/categories/get-transactions", response=ApiResponse)
@permission_required("products_view")
def getAllCategories(request, payload: Optional[dict] = None):
    return CategoryService.getAll(payload, request)


@router.get("/categories/dropdown-list", response=ApiResponse)
@permission_required("products_view")
def getCategoryDropdown(request):
    return CategoryService.dropdownList(request)


@router.delete("/categories/delete", response=ApiResponse)
@permission_required("products_delete")
def deleteCategories(request, payload: DeleteSchema):
    return CategoryService.delete(payload.dict(), request)


@router.patch("/categories/status", response=ApiResponse)
@permission_required("products_update")
def updateCategoryStatus(request, payload: StatusUpdateSchema):
    return CategoryService.updateStatus(payload.dict(), request)


@router.get("/categories/{category_id}", response=ApiResponse)
@permission_required("products_view")
def getCategoryById(request, category_id: int):
    return CategoryService.getById(category_id, request)


@router.put("/categories/{category_id}", response=ApiResponse)
@permission_required("products_update")
def updateCategory(request, category_id: int, payload: CategoryUpdateIn):
    return CategoryService.update(payload.dict(exclude_none=True), request, category_id)

# -------------------------------------------------------- /////////////// -------------------------------------------------------- /////////////// --------------------------------------------------------

@router.post("/brands/", response=ApiResponse)
@permission_required("products_create")
def createBrand(request, payload: BrandIn):
    return BrandService.create(payload.dict(), request)


@router.post("/brands/get-transactions", response=ApiResponse)
@permission_required("products_view")
def getAllBrands(request, payload: Optional[dict] = None):
    return BrandService.getAll(payload, request)


@router.get("/brands/dropdown-list", response=ApiResponse)
@permission_required("products_view")
def getBrandDropdown(request):
    return BrandService.dropdownList(request)


@router.delete("/brands/delete", response=ApiResponse)
@permission_required("products_delete")
def deleteBrands(request, payload: DeleteSchema):
    return BrandService.delete(payload.dict(), request)


@router.patch("/brands/status", response=ApiResponse)
@permission_required("products_update")
def updateBrandStatus(request, payload: StatusUpdateSchema):
    return BrandService.updateStatus(payload.dict(), request)


@router.get("/brands/{brand_id}", response=ApiResponse)
@permission_required("products_view")
def getBrandById(request, brand_id: int):
    return BrandService.getById(brand_id, request)


@router.put("/brands/{brand_id}", response=ApiResponse)
@permission_required("products_update")
def updateBrand(request, brand_id: int, payload: BrandUpdateIn):
    return BrandService.update(payload.dict(exclude_none=True), request, brand_id)

# -------------------------------------------------------- /////////////// -------------------------------------------------------- /////////////// --------------------------------------------------------

@router.post("/unit-groups/", response=ApiResponse)
@permission_required("products_create")
def createUnitGroup(request, payload: UnitGroupIn):
    return UnitGroupService.create(payload.dict(), request)


@router.post("/unit-groups/get-transactions", response=ApiResponse)
@permission_required("products_view")
def getAllUnitGroups(request, payload: Optional[dict] = None):
    return UnitGroupService.getAll(payload, request)


@router.get("/unit-groups/dropdown-list", response=ApiResponse)
@permission_required("products_view")
def getUnitGroupDropdown(request):
    return UnitGroupService.dropdownList(request)


@router.delete("/unit-groups/delete", response=ApiResponse)
@permission_required("products_delete")
def deleteUnitGroups(request, payload: DeleteSchema):
    return UnitGroupService.delete(payload.dict(), request)


@router.patch("/unit-groups/status", response=ApiResponse)
@permission_required("products_update")
def updateUnitGroupStatus(request, payload: StatusUpdateSchema):
    return UnitGroupService.updateStatus(payload.dict(), request)


@router.get("/unit-groups/{unit_group_id}", response=ApiResponse)
@permission_required("products_view")
def getUnitGroupById(request, unit_group_id: int):
    return UnitGroupService.getById(unit_group_id, request)


@router.put("/unit-groups/{unit_group_id}", response=ApiResponse)
@permission_required("products_update")
def updateUnitGroup(request, unit_group_id: int, payload: UnitGroupUpdateIn):
    return UnitGroupService.update(payload.dict(exclude_none=True), request, unit_group_id)

# -------------------------------------------------------- /////////////// -------------------------------------------------------- /////////////// --------------------------------------------------------

@router.post("/units/", response=ApiResponse)
@permission_required("products_create")
def createUnit(request, payload: UnitIn):
    return UnitService.create(payload.dict(), request)


@router.post("/units/get-transactions", response=ApiResponse)
@permission_required("products_view")
def getAllUnits(request, payload: Optional[dict] = None):
    return UnitService.getAll(payload, request)


@router.get("/units/dropdown-list", response=ApiResponse)
@permission_required("products_view")
def getUnitDropdown(request):
    return UnitService.dropdownList(request)


@router.delete("/units/delete", response=ApiResponse)
@permission_required("products_delete")
def deleteUnits(request, payload: DeleteSchema):
    return UnitService.delete(payload.dict(), request)


@router.patch("/units/status", response=ApiResponse)
@permission_required("products_update")
def updateUnitStatus(request, payload: StatusUpdateSchema):
    return UnitService.updateStatus(payload.dict(), request)


@router.get("/units/{unit_id}", response=ApiResponse)
@permission_required("products_view")
def getUnitById(request, unit_id: int):
    return UnitService.getById(unit_id, request)


@router.put("/units/{unit_id}", response=ApiResponse)
@permission_required("products_update")
def updateUnit(request, unit_id: int, payload: UnitUpdateIn):
    return UnitService.update(payload.dict(exclude_none=True), request, unit_id)

# -------------------------------------------------------- /////////////// -------------------------------------------------------- /////////////// --------------------------------------------------------

@router.post("/tax-groups/", response=ApiResponse)
@permission_required("products_create")
def createTaxGroup(request, payload: TaxGroupIn):
    return TaxGroupService.create(payload.dict(), request)


@router.post("/tax-groups/get-transactions", response=ApiResponse)
@permission_required("products_view")
def getAllTaxGroups(request, payload: Optional[dict] = None):
    return TaxGroupService.getAll(payload, request)


@router.get("/tax-groups/dropdown-list", response=ApiResponse)
@permission_required("products_view")
def getTaxGroupDropdown(request):
    return TaxGroupService.dropdownList(request)


@router.delete("/tax-groups/delete", response=ApiResponse)
@permission_required("products_delete")
def deleteTaxGroups(request, payload: DeleteSchema):
    return TaxGroupService.delete(payload.dict(), request)


@router.patch("/tax-groups/status", response=ApiResponse)
@permission_required("products_update")
def updateTaxGroupStatus(request, payload: StatusUpdateSchema):
    return TaxGroupService.updateStatus(payload.dict(), request)


@router.get("/tax-groups/{tax_group_id}", response=ApiResponse)
@permission_required("products_view")
def getTaxGroupById(request, tax_group_id: int):
    return TaxGroupService.getById(tax_group_id, request)


@router.put("/tax-groups/{tax_group_id}", response=ApiResponse)
@permission_required("products_update")
def updateTaxGroup(request, tax_group_id: int, payload: TaxGroupUpdateIn):
    return TaxGroupService.update(payload.dict(exclude_none=True), request, tax_group_id)

# -------------------------------------------------------- /////////////// -------------------------------------------------------- /////////////// --------------------------------------------------------

@router.post("/taxes/", response=ApiResponse)
@permission_required("products_create")
def createTax(request, payload: TaxIn):
    return TaxService.create(payload.dict(), request)


@router.post("/taxes/get-transactions", response=ApiResponse)
@permission_required("products_view")
def getAllTaxes(request, payload: Optional[dict] = None):
    return TaxService.getAll(payload, request)


@router.get("/taxes/dropdown-list", response=ApiResponse)
@permission_required("products_view")
def getTaxDropdown(request):
    return TaxService.dropdownList(request)


@router.delete("/taxes/delete", response=ApiResponse)
@permission_required("products_delete")
def deleteTaxes(request, payload: DeleteSchema):
    return TaxService.delete(payload.dict(), request)


@router.patch("/taxes/status", response=ApiResponse)
@permission_required("products_update")
def updateTaxStatus(request, payload: StatusUpdateSchema):
    return TaxService.updateStatus(payload.dict(), request)


@router.get("/taxes/{tax_id}", response=ApiResponse)
@permission_required("products_view")
def getTaxById(request, tax_id: int):
    return TaxService.getById(tax_id, request)


@router.put("/taxes/{tax_id}", response=ApiResponse)
@permission_required("products_update")
def updateTax(request, tax_id: int, payload: TaxUpdateIn):
    return TaxService.update(payload.dict(exclude_none=True), request, tax_id)

# -------------------------------------------------------- /////////////// -------------------------------------------------------- /////////////// --------------------------------------------------------

@router.post("/products/", response=ApiResponse)
@permission_required("products_create")
def createProduct(request, payload: ProductIn):
    return ProductService.create(payload.dict(), request)


@router.post("/products/get-transactions", response=ApiResponse)
@permission_required("products_view")
def getAllProducts(request, payload: Optional[dict] = None):
    return ProductService.getAll(payload, request)


@router.get("/products/dropdown-list", response=ApiResponse)
@permission_required("products_view")
def getProductDropdown(request):
    return ProductService.dropdownList(request)


@router.delete("/products/delete", response=ApiResponse)
@permission_required("products_delete")
def deleteProducts(request, payload: DeleteSchema):
    return ProductService.delete(payload.dict(), request)


@router.patch("/products/status", response=ApiResponse)
@permission_required("products_update")
def updateProductStatus(request, payload: StatusUpdateSchema):
    return ProductService.updateStatus(payload.dict(), request)


@router.get("/products/{product_id}", response=ApiResponse)
@permission_required("products_view")
def getProductById(request, product_id: int):
    return ProductService.getById(product_id, request)


@router.put("/products/{product_id}", response=ApiResponse)
@permission_required("products_update")
def updateProduct(request, product_id: int, payload: ProductUpdateIn):
    return ProductService.update(payload.dict(exclude_none=True), request, product_id)
