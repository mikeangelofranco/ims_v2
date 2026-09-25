from django import forms
from django.core.validators import MinValueValidator
from django.db.models import Q, QuerySet

from apps.tenancy.context import get_current_tenant

from .models import Category, Location, Product, ProductCustomField


class ProductForm(forms.ModelForm):
    category = forms.ModelChoiceField(queryset=QuerySet(model=Category).none(), required=False)

    class Meta:
        model = Product
        fields = (
            "name",
            "description",
            "image",
            "sku",
            "barcode",
            "category",
            "selling_price",
            "unit_cost",
            "is_active",
            "brand",
            "model",
            "unit_of_measure",
            "has_variants",
        )
        labels = {"selling_price": "Selling price", "unit_cost": "Unit cost"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tenant = get_current_tenant()
        category_filter = Q(is_active=True)
        if self.instance.pk and self.instance.category_id:
            category_filter |= Q(pk=self.instance.category_id)
        self.fields["category"].queryset = Category.objects.filter(category_filter)
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "ui-checkbox" if isinstance(field.widget, forms.CheckboxInput) else "ui-input"
            )
        self.custom_definitions = tuple(ProductCustomField.objects.filter(is_active=True))
        values = (
            dict(self.instance.custom_values.values_list("field_id", "value"))
            if self.instance.pk and not self.instance._state.adding
            else {}
        )
        for definition in self.custom_definitions:
            self.fields[f"custom_{definition.key}"] = forms.CharField(
                max_length=500,
                required=False,
                label=definition.name,
                initial=values.get(definition.pk, ""),
                widget=forms.TextInput(attrs={"class": "ui-input"}),
            )
        self.fields["description"].widget = forms.Textarea(
            attrs={"class": "ui-input", "rows": 3, "maxlength": 500}
        )
        self.fields["unit_of_measure"].required = False
        for name in ("selling_price", "unit_cost"):
            self.fields[name].validators.append(MinValueValidator(0))
            self.fields[name].widget.attrs.update({"min": "0", "step": "0.01"})
        self.fields["barcode"].required = False
        self.fields["image"].widget.attrs["accept"] = ".png,.jpg,.jpeg"

    def full_clean(self):
        super().full_clean()
        for name, field in self.fields.items():
            if name in self._errors:
                field.widget.attrs["aria-invalid"] = "true"
                field.widget.attrs["aria-describedby"] = f"id_{name}_error"

    @property
    def custom_fields(self):
        return [self[f"custom_{definition.key}"] for definition in self.custom_definitions]

    def clean(self):
        data = super().clean()
        data["unit_of_measure"] = data.get("unit_of_measure") or self.instance.unit_of_measure
        for key in ("sku", "barcode"):
            value = (data.get(key) or "").strip()
            data[key] = value or (None if key == "barcode" else "")
            if (
                value
                and Product.objects.filter(**{key: value}).exclude(pk=self.instance.pk).exists()
            ):
                self.add_error(key, f"A product with this {key.upper()} already exists.")
        return data


class OpeningStockForm(forms.Form):
    location = forms.ModelChoiceField(queryset=QuerySet(model=Location).none(), required=False)
    quantity = forms.IntegerField(
        min_value=0, max_value=2147483647, initial=0, required=False, label="Opening Stock"
    )
    minimum_quantity = forms.IntegerField(
        min_value=0, max_value=2147483647, initial=0, required=False, label="Minimum Stock"
    )

    def __init__(self, *args, tracking=True, compact=False, **kwargs):
        self.tracking = tracking
        super().__init__(*args, **kwargs)
        self.fields["location"].queryset = Location.objects.filter(is_active=True)
        locations = self.fields["location"].queryset
        self.single_location = locations.count() <= 1
        self.default_location = locations.filter(is_default=True).first()
        if self.default_location is None and locations.count() == 1:
            self.default_location = locations.first()
        self.fields["location"].initial = self.default_location
        for field in self.fields.values():
            field.widget.attrs["class"] = "ui-input ui-input--compact" if compact else "ui-input"

    def clean(self):
        data = super().clean()
        data["quantity"] = data.get("quantity") or 0
        data["minimum_quantity"] = data.get("minimum_quantity") or 0
        if not self.tracking:
            if data["quantity"] or data["minimum_quantity"]:
                raise forms.ValidationError(
                    "Opening stock and minimum stock must be zero when tracking is disabled."
                )
            return data
        if not data.get("location") and "location" not in self.errors:
            data["location"] = self.default_location
            if self.fields["location"].queryset.exists() and not self.default_location:
                self.add_error("location", "Choose a location for opening stock.")
        return data


class ProductImportForm(forms.Form):
    file = forms.FileField(
        label="Products CSV",
        widget=forms.FileInput(attrs={"accept": ".csv,text/csv", "class": "ui-input"}),
    )

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > 2 * 1024 * 1024:
            raise forms.ValidationError("CSV files must be smaller than 2 MB.")
        return file
