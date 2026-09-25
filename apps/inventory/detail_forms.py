from django import forms
from django.db.models import QuerySet

from .models import Location


class GalleryImageForm(forms.Form):
    image = forms.FileField(label="Product image")
    alt_text = forms.CharField(max_length=160, required=False, label="Image description")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].widget.attrs.update({"accept": ".png,.jpg,.jpeg", "class": "ui-input"})
        self.fields["alt_text"].widget.attrs["class"] = "ui-input"


class StockActionForm(forms.Form):
    location = forms.ModelChoiceField(queryset=QuerySet(model=Location).none(), label="Location")
    destination = forms.ModelChoiceField(
        queryset=QuerySet(model=Location).none(), label="Destination location"
    )
    quantity = forms.IntegerField(min_value=1, max_value=2147483647, label="Quantity")
    delta = forms.IntegerField(min_value=-2147483647, max_value=2147483647, label="Change")
    note = forms.CharField(max_length=240, required=False, label="Note")

    def __init__(self, *args, kind, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        locations = Location.objects.filter(is_active=True)
        for name in ("location", "destination"):
            self.fields[name].queryset = locations
        if kind == "adjust":
            self.fields.pop("quantity")
            self.fields.pop("destination")
        elif kind == "receive":
            self.fields.pop("delta")
            self.fields.pop("destination")
        elif kind == "transfer":
            self.fields.pop("delta")
        else:
            raise ValueError("Unknown stock action")
        for field in self.fields.values():
            field.widget.attrs["class"] = "ui-input ui-input--compact"

    def clean(self):
        data = super().clean()
        if self.kind == "adjust" and data.get("delta") == 0:
            self.add_error("delta", "Enter a non-zero change.")
        if self.kind == "transfer" and data.get("location") == data.get("destination"):
            self.add_error("destination", "Choose a different location.")
        return data
