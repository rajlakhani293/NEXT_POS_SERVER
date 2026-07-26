# type: ignore
from typing import Optional
from ninja import File, Form, Router
from ninja.files import UploadedFile
from apps.accounts.auth import auth_bearer
from apps.catalog.schemas import (
    CategoryIn,
    CategoryUpdateIn,
    ProductAdjustmentIn,
    ProductIn,
    ProductUnitQuantityIn,
    ProductUnitQuantityUpdateIn,
    ProductUpdateIn,
    ScaleRangeIn,
    ScaleRangeUpdateIn,
    TaxGroupIn,
    TaxGroupUpdateIn,
    TaxIn,
    TaxUpdateIn,
    UnitGroupIn,
    UnitGroupUpdateIn,
    UnitIn,
    UnitUpdateIn,
)
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema, payloadData
from apps.catalog.services import (
    CategoryService,
    ProductService,
    ProductStockService,
    ProductUnitQuantityService,
    ScaleRangeService,
    TaxGroupService,
    TaxService,
    UnitGroupService,
    UnitService,
)
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse


router = Router(tags=["catalog"], auth=auth_bearer)
inventoryRouter = Router(tags=["inventory"], auth=auth_bearer)


@router.post("/categories/", response=ApiResponse)
@permissionRequired("pos.create.categories")
def createCategory(request, payload: CategoryIn):
    return CategoryService.create(payloadData(payload), request)


@router.post("/categories/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.categories")
def getAllCategories(request, payload: Optional[dict] = None):
    return CategoryService.getAll(payload, request)


@router.get("/categories", response=ApiResponse)
@permissionRequired("pos.read.categories")
def getCategoriesSourceList(request, parent: Optional[str] = None):
    return CategoryService.getSource(parent=parent == "true", request=request)


@router.get("/categories/dropdown-list", response=ApiResponse)
@permissionRequired("pos.read.categories")
def getCategoryDropdown(request):
    return CategoryService.dropdownList(request)


@router.delete("/categories/delete", response=ApiResponse)
@permissionRequired("pos.delete.categories")
def deleteCategories(request, payload: BulkIdsSchema):
    return CategoryService.delete(payloadData(payload), request)


@router.patch("/categories/status", response=ApiResponse)
@permissionRequired("pos.update.categories")
def updateCategoryStatus(request, payload: StatusUpdateSchema):
    return CategoryService.updateStatus(payloadData(payload), request)


@router.post("/categories/reorder", response=ApiResponse)
@permissionRequired("pos.update.categories")
def reorderCategories(request, payload: dict):
    return CategoryService.reorderCategories(payload, request)


@router.get("/categories/{category_id}/compute-products", response=ApiResponse)
@permissionRequired("pos.update.categories")
def computeCategoryProducts(request, category_id: int):
    return CategoryService.computeProducts(category_id, request)


@router.get("/categories/pos", response=ApiResponse)
@permissionRequired("pos.read.categories")
def getPOSCategoriesRoot(request):
    return CategoryService.getPOSCategories(request, parent_id=None)


@router.get("/categories/pos/{parent_id}", response=ApiResponse)
@permissionRequired("pos.read.categories")
def getPOSCategoriesSub(request, parent_id: str):
    return CategoryService.getPOSCategories(request, parent_id=parent_id)


@router.get("/categories/{category_id}/products", response=ApiResponse)
@permissionRequired("pos.read.categories")
def getCategoryProducts(request, category_id: int):
    return CategoryService.getProducts(category_id, request)


@router.get("/categories/{category_id}/variations", response=ApiResponse)
@permissionRequired("pos.read.categories")
def getCategoryVariations(request, category_id: int):
    return CategoryService.getProducts(category_id, request, variations_only=True)


@router.get("/categories/{category_id}", response=ApiResponse)
@permissionRequired("pos.read.categories")
def getCategoryById(request, category_id: int):
    return CategoryService.getById(category_id, request)


@router.put("/categories/{category_id}", response=ApiResponse)
@permissionRequired("pos.update.categories")
def updateCategory(request, category_id: int, payload: CategoryUpdateIn):
    return CategoryService.update(payloadData(payload, exclude_none=True), request, category_id)


@router.delete("/categories/{category_id}", response=ApiResponse)
@permissionRequired("pos.delete.categories")
def deleteCategorySource(request, category_id: int):
    return CategoryService.delete({"ids": [category_id]}, request)


@router.post("/unit-groups/", response=ApiResponse)
@permissionRequired("pos.create.products-units")
def createUnitGroup(request, payload: UnitGroupIn):
    return UnitGroupService.create(payloadData(payload), request)


@router.post("/unit-groups/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getAllUnitGroups(request, payload: Optional[dict] = None):
    return UnitGroupService.getAll(payload, request)


@router.get("/unit-groups/dropdown-list", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getUnitGroupDropdown(request):
    return UnitGroupService.dropdownList(request)


@router.get("/unit-groups", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getUnitGroupsSourceList(request):
    return UnitGroupService.getSource(request=request)


@router.get("/units-groups", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getUnitsGroupsSourceList(request):
    return UnitGroupService.getSource(request=request)


@router.delete("/unit-groups/delete", response=ApiResponse)
@permissionRequired("pos.delete.products-units")
def deleteUnitGroups(request, payload: BulkIdsSchema):
    return UnitGroupService.delete(payloadData(payload), request)


@router.patch("/unit-groups/status", response=ApiResponse)
@permissionRequired("pos.update.products-units")
def updateUnitGroupStatus(request, payload: StatusUpdateSchema):
    return UnitGroupService.updateStatus(payloadData(payload), request)


@router.delete("/unit-groups/{unit_group_id}", response=ApiResponse)
@permissionRequired("pos.delete.products-units")
def deleteUnitGroupSource(request, unit_group_id: int):
    return UnitGroupService.delete({"ids": [unit_group_id]}, request)


@router.delete("/units-groups/{unit_group_id}", response=ApiResponse)
@permissionRequired("pos.delete.products-units")
def deleteUnitsGroupSourceAlias(request, unit_group_id: int):
    return UnitGroupService.delete({"ids": [unit_group_id]}, request)


@router.get("/unit-groups/{unit_group_id}/units", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getUnitGroupUnits(request, unit_group_id: int):
    return UnitGroupService.getGroupUnits(unit_group_id, request)


@router.get("/units-groups/{unit_group_id}/units", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getUnitsGroupUnitsSourceAlias(request, unit_group_id: int):
    return UnitGroupService.getGroupUnits(unit_group_id, request)


@router.get("/units-groups/{unit_group_id}", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getUnitsGroupSourceDetail(request, unit_group_id: int):
    return UnitGroupService.getSource(unit_group_id, request=request)


@router.get("/unit-groups/{unit_group_id}", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getUnitGroupById(request, unit_group_id: int):
    return UnitGroupService.getById(unit_group_id, request)


@router.put("/unit-groups/{unit_group_id}", response=ApiResponse)
@permissionRequired("pos.update.products-units")
def updateUnitGroup(request, unit_group_id: int, payload: UnitGroupUpdateIn):
    return UnitGroupService.update(payloadData(payload, exclude_none=True), request, unit_group_id)

@router.post("/units/", response=ApiResponse)
@permissionRequired("pos.create.products-units")
def createUnit(request, payload: UnitIn):
    return UnitService.create(payloadData(payload), request)


@router.post("/units/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getAllUnits(request, payload: Optional[dict] = None):
    return UnitService.getAll(payload, request)


@router.get("/units/dropdown-list", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getUnitDropdown(request):
    return UnitService.dropdownList(request)


@router.get("/units", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getUnitsSourceList(request):
    return UnitService.getSource(request=request)


@router.delete("/units/delete", response=ApiResponse)
@permissionRequired("pos.delete.products-units")
def deleteUnits(request, payload: BulkIdsSchema):
    return UnitService.delete(payloadData(payload), request)


@router.patch("/units/status", response=ApiResponse)
@permissionRequired("pos.update.products-units")
def updateUnitStatus(request, payload: StatusUpdateSchema):
    return UnitService.updateStatus(payloadData(payload), request)


@router.delete("/units/{unit_id}", response=ApiResponse)
@permissionRequired("pos.delete.products-units")
def deleteUnitSource(request, unit_id: int):
    return UnitService.delete({"ids": [unit_id]}, request)


@router.get("/units/{unit_id}/group", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getUnitParentGroup(request, unit_id: int):
    return UnitService.getUnitParentGroup(unit_id, request)


@router.get("/units/{unit_id}/siblings", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getSiblingUnits(request, unit_id: int):
    return UnitService.getSiblingUnits(unit_id, request)


@router.get("/units/{unit_id}", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getUnitById(request, unit_id: int):
    return UnitService.getById(unit_id, request)


@router.put("/units/{unit_id}", response=ApiResponse)
@permissionRequired("pos.update.products-units")
def updateUnit(request, unit_id: int, payload: UnitUpdateIn):
    return UnitService.update(payloadData(payload, exclude_none=True), request, unit_id)

@router.post("/tax-groups/", response=ApiResponse)
@permissionRequired("pos.create.taxes")
def createTaxGroup(request, payload: TaxGroupIn):
    return TaxGroupService.create(payloadData(payload), request)


@router.post("/tax-groups/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.taxes")
def getAllTaxGroups(request, payload: Optional[dict] = None):
    return TaxGroupService.getAll(payload, request)


@router.get("/tax-groups/dropdown-list", response=ApiResponse)
@permissionRequired("pos.read.taxes")
def getTaxGroupDropdown(request):
    return TaxGroupService.dropdownList(request)


@router.get("/tax-groups", response=ApiResponse)
@permissionRequired("pos.read.taxes")
def getTaxGroupsSourceList(request):
    return TaxGroupService.getSource(request=request)


@router.delete("/tax-groups/delete", response=ApiResponse)
@permissionRequired("pos.delete.taxes")
def deleteTaxGroups(request, payload: BulkIdsSchema):
    return TaxGroupService.delete(payloadData(payload), request)


@router.patch("/tax-groups/status", response=ApiResponse)
@permissionRequired("pos.update.taxes")
def updateTaxGroupStatus(request, payload: StatusUpdateSchema):
    return TaxGroupService.updateStatus(payloadData(payload), request)


@router.get("/tax-groups/{tax_group_id}", response=ApiResponse)
@permissionRequired("pos.read.taxes")
def getTaxGroupById(request, tax_group_id: int):
    return TaxGroupService.getById(tax_group_id, request)


@router.put("/tax-groups/{tax_group_id}", response=ApiResponse)
@permissionRequired("pos.update.taxes")
def updateTaxGroup(request, tax_group_id: int, payload: TaxGroupUpdateIn):
    return TaxGroupService.update(payloadData(payload, exclude_none=True), request, tax_group_id)

@router.post("/taxes/", response=ApiResponse)
@permissionRequired("pos.create.taxes")
def createTax(request, payload: TaxIn):
    return TaxService.create(payloadData(payload), request)


@router.post("/taxes/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.taxes")
def getAllTaxes(request, payload: Optional[dict] = None):
    return TaxService.getAll(payload, request)


@router.get("/taxes/dropdown-list", response=ApiResponse)
@permissionRequired("pos.read.taxes")
def getTaxDropdown(request):
    return TaxService.dropdownList(request)


@router.delete("/taxes/delete", response=ApiResponse)
@permissionRequired("pos.delete.taxes")
def deleteTaxes(request, payload: BulkIdsSchema):
    return TaxService.delete(payloadData(payload), request)


@router.patch("/taxes/status", response=ApiResponse)
@permissionRequired("pos.update.taxes")
def updateTaxStatus(request, payload: StatusUpdateSchema):
    return TaxService.updateStatus(payloadData(payload), request)


@router.get("/taxes/groups", response=ApiResponse)
@permissionRequired("pos.read.taxes")
def getTaxesGroupsSourceList(request):
    return TaxGroupService.getSource(request=request)


@router.get("/taxes/groups/{tax_group_id}", response=ApiResponse)
@permissionRequired("pos.read.taxes")
def getTaxesGroupSourceDetail(request, tax_group_id: int):
    return TaxGroupService.getSource(tax_group_id, request=request)


@router.get("/taxes", response=ApiResponse)
@permissionRequired("pos.read.taxes")
def getTaxesSourceList(request):
    return TaxService.getSource(request=request)


@router.get("/taxes/{tax_id}", response=ApiResponse)
@permissionRequired("pos.read.taxes")
def getTaxById(request, tax_id: int):
    return TaxService.getById(tax_id, request)


@router.put("/taxes/{tax_id}", response=ApiResponse)
@permissionRequired("pos.update.taxes")
def updateTax(request, tax_id: int, payload: TaxUpdateIn):
    return TaxService.update(payloadData(payload, exclude_none=True), request, tax_id)


@router.delete("/taxes/{tax_id}", response=ApiResponse)
@permissionRequired("pos.delete.taxes")
def deleteTaxSource(request, tax_id: int):
    return TaxService.delete({"ids": [tax_id]}, request)


@router.post("/scale-ranges/", response=ApiResponse)
@permissionRequired("pos.create.products")
def createScaleRange(request, payload: ScaleRangeIn):
    return ScaleRangeService.create(payloadData(payload), request)


@router.post("/scale-ranges/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.products")
def getAllScaleRanges(request, payload: Optional[dict] = None):
    return ScaleRangeService.getAll(payload, request)


@router.get("/scale-ranges/dropdown-list", response=ApiResponse)
@permissionRequired("pos.read.products")
def getScaleRangeDropdown(request):
    return ScaleRangeService.dropdownList(request)


@router.delete("/scale-ranges/delete", response=ApiResponse)
@permissionRequired("pos.delete.products")
def deleteScaleRanges(request, payload: BulkIdsSchema):
    return ScaleRangeService.delete(payloadData(payload), request)


@router.patch("/scale-ranges/status", response=ApiResponse)
@permissionRequired("pos.update.products")
def updateScaleRangeStatus(request, payload: StatusUpdateSchema):
    return ScaleRangeService.updateStatus(payloadData(payload), request)


@router.get("/scale-ranges/{scale_range_id}", response=ApiResponse)
@permissionRequired("pos.read.products")
def getScaleRangeById(request, scale_range_id: int):
    return ScaleRangeService.getById(scale_range_id, request)


@router.put("/scale-ranges/{scale_range_id}", response=ApiResponse)
@permissionRequired("pos.update.products")
def updateScaleRange(request, scale_range_id: int, payload: ScaleRangeUpdateIn):
    return ScaleRangeService.update(scale_range_id, payloadData(payload, exclude_none=True), request)


@router.post("/products/", response=ApiResponse)
@permissionRequired("pos.create.products")
def createProduct(request, payload: Form[ProductIn], image: File[Optional[UploadedFile]] = None):
    return ProductService.create(payloadData(payload, exclude_unset=True), request, image=image)


@router.post("/products/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.products")
def getAllProducts(request, payload: Optional[dict] = None):
    return ProductService.getAll(payload, request)


@router.get("/products", response=ApiResponse)
@permissionRequired("pos.read.products")
def getProductsSourceList(request):
    return ProductService.getProducts(request)


@router.post("/products/search", response=ApiResponse)
@permissionRequired("pos.read.products")
def searchProducts(request, payload: Optional[dict] = None):
    return ProductService.searchProduct(payload, request)


@router.get("/products/all/variations", response=ApiResponse)
@permissionRequired("pos.read.products")
def getAllProductVariations(request):
    return ProductService.getVariations(request)


@router.get("/products/dropdown-list", response=ApiResponse)
@permissionRequired("pos.read.products")
def getProductDropdown(request):
    return ProductService.dropdownList(request)


@router.delete("/products/delete", response=ApiResponse)
@permissionRequired("pos.delete.products")
def deleteProducts(request, payload: BulkIdsSchema):
    return ProductService.delete(payloadData(payload), request)


@router.patch("/products/status", response=ApiResponse)
@permissionRequired("pos.update.products")
def updateProductStatus(request, payload: StatusUpdateSchema):
    return ProductService.updateStatus(payloadData(payload), request)


@router.post("/products/adjustments", response=ApiResponse)
@permissionRequired("pos.make.products-adjustments")
def adjustProductStock(request, payload: ProductAdjustmentIn):
    return ProductStockService.applyManualAdjustment(payloadData(payload), request)


@router.post("/products/reorder", response=ApiResponse)
@permissionRequired("pos.update.products")
def reorderProducts(request, payload: dict):
    return ProductService.reorderProducts(payload, request)


@router.delete("/products/{product_id}", response=ApiResponse)
@permissionRequired("pos.delete.products")
def deleteProductSource(request, product_id: int):
    return ProductService.delete({"ids": [product_id]}, request)


@router.get("/products/search/using-barcode/{reference}", response=ApiResponse)
@permissionRequired("pos.read.products")
def searchProductUsingBarcode(request, reference: str):
    return ProductService.searchUsingBarcode(reference, request)


@router.get("/products/{product_id}/units/quantities", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getProductUnitQuantities(request, product_id: int):
    return ProductUnitQuantityService.getAll(product_id, request)


@router.get("/products/{product_id}/units", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getProductUnitsSourceAlias(request, product_id: int):
    return ProductUnitQuantityService.getAll(product_id, request)


@router.get("/products/{product_id}/units/{unit_id}/quantity", response=ApiResponse)
@permissionRequired("pos.read.products-units")
def getProductUnitQuantitySourceAlias(request, product_id: int, unit_id: int):
    return ProductUnitQuantityService.getByProductAndUnit(product_id, unit_id, request)


@router.post("/products/{product_id}/units/quantities", response=ApiResponse)
@permissionRequired("pos.update.products-units")
def createProductUnitQuantity(request, product_id: int, payload: ProductUnitQuantityIn):
    return ProductUnitQuantityService.create(product_id, payloadData(payload), request)


@router.post("/products/{product_id}/units/conversion", response=ApiResponse)
@permissionRequired("pos.update.products")
def convertProductUnits(request, product_id: int, payload: dict):
    return ProductService.convertUnitQuantities(product_id, payload, request)


@router.put("/products/{product_id}/units/quantities/{unit_quantity_id}", response=ApiResponse)
@permissionRequired("pos.update.products-units")
def updateProductUnitQuantity(
    request,
    product_id: int,
    unit_quantity_id: int,
    payload: ProductUnitQuantityUpdateIn,
):
    return ProductUnitQuantityService.update(product_id, unit_quantity_id, payloadData(payload, exclude_none=True), request)


@router.delete("/products/{product_id}/units/quantities/{unit_quantity_id}", response=ApiResponse)
@permissionRequired("pos.delete.products-units")
def deleteProductUnitQuantity(request, product_id: int, unit_quantity_id: int):
    return ProductUnitQuantityService.delete(product_id, unit_quantity_id, request)


@router.get("/products/{product_id}/variations", response=ApiResponse)
@permissionRequired("pos.read.products")
def getProductVariations(request, product_id: int):
    return ProductService.getVariations(request, product_id)


@router.get("/products/{product_id}/refresh-prices", response=ApiResponse)
@permissionRequired("pos.read.products")
def refreshProductPrices(request, product_id: int):
    return ProductService.getByIdentifier(product_id, request)


@router.get("/products/{product_id}/reset", response=ApiResponse)
@permissionRequired("pos.read.products")
def resetProduct(request, product_id: int):
    return ProductService.resetProduct(product_id, request)


@router.get("/products/{product_id}/history", response=ApiResponse)
@permissionRequired("pos.read.products")
def getProductHistory(request, product_id: int):
    return ProductService.getHistory(product_id, request)


@router.get("/products/{product_id}/procurements", response=ApiResponse)
@permissionRequired("pos.read.products")
def getProductProcurements(request, product_id: int):
    return ProductService.getProcuredProducts(product_id, request)


@router.get("/products/{product_id}", response=ApiResponse)
@permissionRequired("pos.read.products")
def getProductById(request, product_id: int):
    return ProductService.getById(product_id, request)


@router.put("/products/{product_id}", response=ApiResponse)
@permissionRequired("pos.update.products")
def updateProduct(
    request,
    product_id: int,
    payload: Form[ProductUpdateIn],
    image: File[Optional[UploadedFile]] = None,
):
    return ProductService.update(payloadData(payload, exclude_unset=True), request, product_id, image=image)


@router.post("/products/{product_id}/gallery", response=ApiResponse)
@permissionRequired("pos.update.products")
def addProductGalleryImage(request, product_id: int, image: UploadedFile = File(...)):
    return ProductService.addGalleryImage(product_id, image, request)


@router.delete("/products/{product_id}/gallery/{gallery_id}", response=ApiResponse)
@permissionRequired("pos.update.products")
def deleteProductGalleryImage(request, product_id: int, gallery_id: int):
    return ProductService.deleteGalleryImage(product_id, gallery_id, request)


@inventoryRouter.post("/ledger/get-transactions", response=ApiResponse)
@permissionRequired("inventory_view")
def getInventoryLedger(request, payload: Optional[dict] = None):
    return ProductStockService.stockFlow(payload, request)


@inventoryRouter.post("/adjustments/get-transactions", response=ApiResponse)
@permissionRequired("inventory_view")
def getInventoryAdjustments(request, payload: Optional[dict] = None):
    return ProductStockService.adjustments(payload, request)


@inventoryRouter.post("/adjustments/", response=ApiResponse)
@permissionRequired("inventory_adjust")
def createInventoryAdjustment(request, payload: ProductAdjustmentIn):
    return ProductStockService.applyManualAdjustment(payloadData(payload), request)


@inventoryRouter.delete("/adjustments/delete", response=ApiResponse)
@permissionRequired("inventory_adjust")
def deleteInventoryAdjustments(request, payload: BulkIdsSchema):
    return ProductStockService.deleteAdjustments(payloadData(payload), request)


@inventoryRouter.patch("/adjustments/status", response=ApiResponse)
@permissionRequired("inventory_adjust")
def updateInventoryAdjustmentStatus(request, payload: StatusUpdateSchema):
    return ProductStockService.updateAdjustmentStatus(payloadData(payload), request)
