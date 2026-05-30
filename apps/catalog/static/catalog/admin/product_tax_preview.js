(function () {
  let isUpdatingSellingPrice = false

  function getPreviewElement() {
    const row = document.querySelector(".field-tax_amount_preview")
    if (!row) return null
    return row.querySelector(".readonly") || row
  }

  function updatePreview(options) {
    const shouldSyncSellingPrice = options?.syncSellingPrice === true
    const taxGroup = document.getElementById("id_tax_group")
    const sellingPrice = document.getElementById("id_selling_price")
    const isTaxInclusive = document.getElementById("id_is_tax_inclusive")
    const preview = getPreviewElement()

    if (!taxGroup || !sellingPrice || !isTaxInclusive || !preview) return

    if (isTaxInclusive.checked && !sellingPrice.dataset.baseSellingPrice) {
      sellingPrice.dataset.baseSellingPrice = sellingPrice.value || "0"
    }

    const baseSellingPrice = isTaxInclusive.checked
      ? sellingPrice.dataset.baseSellingPrice || sellingPrice.value || "0"
      : sellingPrice.value || "0"

    const params = new URLSearchParams({
      tax_group_id: taxGroup.value || "",
      selling_price: baseSellingPrice,
      is_tax_inclusive: isTaxInclusive.checked ? "true" : "false",
    })

    fetch(`/admin/catalog/product/tax-preview/?${params.toString()}`, {
      credentials: "same-origin",
    })
      .then((response) => response.json())
      .then((data) => {
        preview.textContent = data.preview || ""
        if (shouldSyncSellingPrice && isTaxInclusive.checked && data.amount_after_tax) {
          isUpdatingSellingPrice = true
          sellingPrice.value = data.amount_after_tax
          isUpdatingSellingPrice = false
        }
      })
      .catch(() => {
        preview.textContent = "Unable to calculate tax"
      })
  }

  document.addEventListener("DOMContentLoaded", function () {
    const taxGroup = document.getElementById("id_tax_group")
    const sellingPrice = document.getElementById("id_selling_price")
    const isTaxInclusive = document.getElementById("id_is_tax_inclusive")

    if (taxGroup) {
      taxGroup.addEventListener("change", function () {
        updatePreview({ syncSellingPrice: true })
      })
    }
    if (sellingPrice) {
      sellingPrice.addEventListener("input", function () {
        if (isUpdatingSellingPrice) return
        sellingPrice.dataset.baseSellingPrice = sellingPrice.value || "0"
        updatePreview({ syncSellingPrice: false })
      })
      sellingPrice.addEventListener("change", function () {
        if (isUpdatingSellingPrice) return
        sellingPrice.dataset.baseSellingPrice = sellingPrice.value || "0"
        updatePreview({ syncSellingPrice: true })
      })
    }
    if (isTaxInclusive) {
      isTaxInclusive.addEventListener("change", function () {
        if (isTaxInclusive.checked) {
          sellingPrice.dataset.baseSellingPrice = sellingPrice.value || "0"
        } else if (sellingPrice.dataset.baseSellingPrice) {
          isUpdatingSellingPrice = true
          sellingPrice.value = sellingPrice.dataset.baseSellingPrice
          sellingPrice.dataset.baseSellingPrice = ""
          isUpdatingSellingPrice = false
        }
        updatePreview({ syncSellingPrice: true })
      })
    }

    updatePreview({ syncSellingPrice: false })
  })
})()
