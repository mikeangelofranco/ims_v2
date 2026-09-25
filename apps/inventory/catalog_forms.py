from django import forms
from django.db.models import Q
from django.utils.text import slugify

from .models import Category, ProductCustomField


class CategoryCreateForm(forms.Form):
    name = forms.CharField(
        max_length=120, label="Category Name", widget=forms.TextInput(attrs={"class": "ui-input"})
    )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if (
            Category.objects.filter(name__iexact=name).exists()
            or Category.objects.filter(slug=slugify(name)[:120]).exists()
        ):
            raise forms.ValidationError("This category already exists in your workspace.")
        return name


CATEGORY_ICONS = (
    ("folder", "Folder"),
    ("headphones", "Audio"),
    ("plug", "Power and chargers"),
    ("link", "Cables and connectivity"),
    ("battery-charging", "Power and batteries"),
    ("box", "Accessories"),
    ("briefcase-business", "Office supplies"),
    ("wifi", "Networking"),
    ("archive", "Archived items"),
)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "code", "description", "icon", "is_active")
        labels = {"is_active": "Category status"}
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "maxlength": 240}),
            "icon": forms.Select(choices=CATEGORY_ICONS),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "ui-checkbox" if isinstance(field.widget, forms.CheckboxInput) else "ui-input"
            )
        self.fields["name"].widget.attrs["placeholder"] = "Enter category name"
        self.fields["code"].widget.attrs["placeholder"] = "Leave blank to auto-generate"
        self.fields["code"].required = False
        self.fields["description"].widget.attrs["placeholder"] = "Describe this category"

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        matches = Category.objects.filter(Q(name__iexact=name) | Q(slug=slugify(name)[:120]))
        if self.instance.pk:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise forms.ValidationError("This category already exists in your workspace.")
        return name

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().upper()
        if not code and self.instance.pk:
            return self.instance.code
        if code:
            matches = Category.objects.filter(code__iexact=code)
            if self.instance.pk:
                matches = matches.exclude(pk=self.instance.pk)
            if matches.exists():
                raise forms.ValidationError("This category code already exists in your workspace.")
        return code


class CustomFieldCreateForm(forms.Form):
    name = forms.CharField(
        max_length=80, label="Field Name", widget=forms.TextInput(attrs={"class": "ui-input"})
    )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        key = slugify(name)[:80]
        if key in ("brand", "model") or ProductCustomField.objects.filter(key=key).exists():
            raise forms.ValidationError("This field already exists in your workspace.")
        return name
