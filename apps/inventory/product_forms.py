from django import forms

from .forms import ProductForm
from .models import UnitOfMeasure
from .product_services import generate_product_sku


class ProductCreateForm(ProductForm):
    sku = forms.CharField(max_length=80, required=False, label="SKU")
    is_active = forms.TypedChoiceField(
        choices=(("active", "Active"), ("inactive", "Inactive")),
        coerce=lambda value: value == "active",
        initial="active",
        label="Product Status",
    )

    class Meta(ProductForm.Meta):
        fields = (*ProductForm.Meta.fields, "track_inventory")
        widgets = {"description": forms.Textarea(attrs={"rows": 3, "maxlength": 500})}
        labels = {
            "name": "Product Name",
            "selling_price": "Selling Price",
            "unit_cost": "Cost Price",
            "track_inventory": "Track Inventory",
            "unit_of_measure": "Unit of Measure",
            "has_variants": "Has Variants",
            "brand": "Brand",
            "model": "Model",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].required = True
        self.fields["category"].empty_label = "Select a category"
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "ui-input ui-input--compact"
        self.fields["unit_cost"].required = False
        self.fields["unit_of_measure"].required = False
        self.fields["unit_of_measure"].initial = UnitOfMeasure.PIECE
        placeholders = {
            "name": "Enter product name",
            "sku": "Enter SKU or leave blank to auto-generate",
            "barcode": "Enter barcode (optional)",
            "description": "Enter product description (optional)",
            "brand": "Enter brand (optional)",
            "model": "Enter model (optional)",
            "selling_price": "0.00",
            "unit_cost": "0.00",
        }
        for name, text in placeholders.items():
            self.fields[name].widget.attrs["placeholder"] = text
        for name in ("track_inventory", "has_variants"):
            self.fields[name].widget.attrs["class"] = "ui-switch__input"
        # Boolean model defaults must be expressed in the select's string vocabulary.
        if not self.is_bound:
            self.initial["is_active"] = "active"

    def clean_sku(self):
        return self.cleaned_data["sku"].strip() or generate_product_sku()

    def clean_unit_cost(self):
        return self.cleaned_data.get("unit_cost") or 0

    def clean_unit_of_measure(self):
        return self.cleaned_data.get("unit_of_measure") or UnitOfMeasure.PIECE
