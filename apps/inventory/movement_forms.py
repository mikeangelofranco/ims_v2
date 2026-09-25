from django import forms
from django.db.models import QuerySet

from .models import Location, Product


class MovementActionForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=QuerySet(model=Product).none(), label="Product"
    )
    location = forms.ModelChoiceField(
        queryset=QuerySet(model=Location).none(), label="Location"
    )
    destination = forms.ModelChoiceField(
        queryset=QuerySet(model=Location).none(),
        required=False,
        label="Destination location",
    )
    quantity = forms.IntegerField(min_value=1, max_value=2147483647)
    delta = forms.IntegerField(
        min_value=-2147483647, max_value=2147483647, required=False, label="Change"
    )
    note = forms.CharField(max_length=240, required=False, label="Remarks")

    def __init__(self, *args, kind, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        self.fields["product"].queryset = Product.objects.filter(
            is_active=True, track_inventory=True
        ).order_by("name")
        locations = Location.objects.filter(is_active=True).order_by("name")
        self.fields["location"].queryset = locations
        self.fields["destination"].queryset = locations
        if kind == "adjust":
            self.fields.pop("quantity")
            self.fields.pop("destination")
            self.fields["delta"].required = True
        elif kind == "receive":
            self.fields.pop("delta")
            self.fields.pop("destination")
        elif kind == "transfer":
            self.fields.pop("delta")
            self.fields["destination"].required = True
        else:
            raise ValueError("Unknown stock action")
        for field in self.fields.values():
            field.widget.attrs["class"] = "ui-input"

    def clean(self):
        data = super().clean()
        if self.kind == "adjust" and data.get("delta") == 0:
            self.add_error("delta", "Enter a non-zero change.")
        if self.kind == "transfer" and data.get("location") == data.get("destination"):
            self.add_error("destination", "Choose a different location.")
        return data
