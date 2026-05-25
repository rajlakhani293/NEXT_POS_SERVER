from apps.catalog.services import CatalogService
from apps.common.responses import success_response


class CatalogController:
    @staticmethod
    def listCategories(request):
        return success_response(
            "Categories fetched successfully.",
            data=CatalogService.listCategories(request.user),
        )

    @staticmethod
    def createCategory(request, payload):
        return success_response(
            "Category created successfully.",
            data=CatalogService.createCategory(request.user, payload),
        )

    @staticmethod
    def updateCategory(request, category_id, payload):
        return success_response(
            "Category updated successfully.",
            data=CatalogService.updateCategory(request.user, category_id, payload),
        )

    @staticmethod
    def deleteCategory(request, category_id):
        return success_response(
            "Category deleted successfully.",
            data=CatalogService.deleteCategory(request.user, category_id),
        )

    @staticmethod
    def listBrands(request):
        return success_response(
            "Brands fetched successfully.",
            data=CatalogService.listBrands(request.user),
        )

    @staticmethod
    def createBrand(request, payload):
        return success_response(
            "Brand created successfully.",
            data=CatalogService.createBrand(request.user, payload),
        )

    @staticmethod
    def updateBrand(request, brand_id, payload):
        return success_response(
            "Brand updated successfully.",
            data=CatalogService.updateBrand(request.user, brand_id, payload),
        )

    @staticmethod
    def deleteBrand(request, brand_id):
        return success_response(
            "Brand deleted successfully.",
            data=CatalogService.deleteBrand(request.user, brand_id),
        )

    @staticmethod
    def listUnitGroups(request):
        return success_response(
            "Unit groups fetched successfully.",
            data=CatalogService.listUnitGroups(request.user),
        )

    @staticmethod
    def createUnitGroup(request, payload):
        return success_response(
            "Unit group created successfully.",
            data=CatalogService.createUnitGroup(request.user, payload),
        )

    @staticmethod
    def updateUnitGroup(request, unit_group_id, payload):
        return success_response(
            "Unit group updated successfully.",
            data=CatalogService.updateUnitGroup(request.user, unit_group_id, payload),
        )

    @staticmethod
    def deleteUnitGroup(request, unit_group_id):
        return success_response(
            "Unit group deleted successfully.",
            data=CatalogService.deleteUnitGroup(request.user, unit_group_id),
        )

    @staticmethod
    def listUnits(request):
        return success_response(
            "Units fetched successfully.",
            data=CatalogService.listUnits(request.user),
        )

    @staticmethod
    def createUnit(request, payload):
        return success_response(
            "Unit created successfully.",
            data=CatalogService.createUnit(request.user, payload),
        )

    @staticmethod
    def updateUnit(request, unit_id, payload):
        return success_response(
            "Unit updated successfully.",
            data=CatalogService.updateUnit(request.user, unit_id, payload),
        )

    @staticmethod
    def deleteUnit(request, unit_id):
        return success_response(
            "Unit deleted successfully.",
            data=CatalogService.deleteUnit(request.user, unit_id),
        )

    @staticmethod
    def listTaxGroups(request):
        return success_response(
            "Tax groups fetched successfully.",
            data=CatalogService.listTaxGroups(request.user),
        )

    @staticmethod
    def createTaxGroup(request, payload):
        return success_response(
            "Tax group created successfully.",
            data=CatalogService.createTaxGroup(request.user, payload),
        )

    @staticmethod
    def updateTaxGroup(request, tax_group_id, payload):
        return success_response(
            "Tax group updated successfully.",
            data=CatalogService.updateTaxGroup(request.user, tax_group_id, payload),
        )

    @staticmethod
    def deleteTaxGroup(request, tax_group_id):
        return success_response(
            "Tax group deleted successfully.",
            data=CatalogService.deleteTaxGroup(request.user, tax_group_id),
        )

    @staticmethod
    def listTaxes(request):
        return success_response(
            "Taxes fetched successfully.",
            data=CatalogService.listTaxes(request.user),
        )

    @staticmethod
    def createTax(request, payload):
        return success_response(
            "Tax created successfully.",
            data=CatalogService.createTax(request.user, payload),
        )

    @staticmethod
    def updateTax(request, tax_id, payload):
        return success_response(
            "Tax updated successfully.",
            data=CatalogService.updateTax(request.user, tax_id, payload),
        )

    @staticmethod
    def deleteTax(request, tax_id):
        return success_response(
            "Tax deleted successfully.",
            data=CatalogService.deleteTax(request.user, tax_id),
        )

    @staticmethod
    def listProducts(request):
        return success_response(
            "Products fetched successfully.",
            data=CatalogService.listProducts(request.user),
        )

    @staticmethod
    def createProduct(request, payload):
        return success_response(
            "Product created successfully.",
            data=CatalogService.createProduct(request.user, payload),
        )

    @staticmethod
    def updateProduct(request, product_id, payload):
        return success_response(
            "Product updated successfully.",
            data=CatalogService.updateProduct(request.user, product_id, payload),
        )

    @staticmethod
    def deleteProduct(request, product_id):
        return success_response(
            "Product deleted successfully.",
            data=CatalogService.deleteProduct(request.user, product_id),
        )
