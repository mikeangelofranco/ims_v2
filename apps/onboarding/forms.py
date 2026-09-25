import re

from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.businesses.models import CompanySize, Currency, Industry
from apps.tenancy.models import Tenant, TenantDomain, TenantMembership
from apps.tenancy.validators import validate_workspace_logo, validate_workspace_slug

User = get_user_model()

TIMEZONE_CHOICES = (
    ("Asia/Manila", "Asia/Manila (GMT+08:00)"),
    ("Asia/Singapore", "Asia/Singapore (GMT+08:00)"),
    ("Asia/Tokyo", "Asia/Tokyo (GMT+09:00)"),
    ("UTC", "UTC (GMT+00:00)"),
    ("Europe/London", "Europe/London"),
    ("America/New_York", "America/New_York"),
)


class StyledFormMixin:
    def apply_widget_styles(self):
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-input"
            field.widget.attrs["class"] = css_class
            if field.required:
                field.widget.attrs["aria-required"] = "true"

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["aria-invalid"] = "true"
                widget.attrs["aria-describedby"] = f"id_{name}_error"


class AccountCreationForm(StyledFormMixin, forms.Form):
    first_name = forms.CharField(
        max_length=150,
        label="First name",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter your first name",
                "data-mobile-placeholder": "First name",
                "autocomplete": "given-name",
            }
        ),
    )
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={
                "placeholder": "Enter your email address",
                "data-mobile-placeholder": "Email address",
                "autocomplete": "email",
            }
        ),
    )
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Create a strong password",
                "data-mobile-placeholder": "Password",
                "autocomplete": "new-password",
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields["password"].required = False
            self.fields["password"].widget.attrs.update(
                {
                    "placeholder": "Leave blank to keep your password",
                    "data-mobile-placeholder": "Password (optional)",
                }
            )
        self.apply_widget_styles()

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).lower()
        users = User.objects.filter(email__iexact=email)
        if self.user is not None:
            users = users.exclude(pk=self.user.pk)
        if users.exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not password and self.user is not None:
            return password
        password_validation.validate_password(password)
        if not re.search(r"[A-Za-z]", password):
            raise ValidationError("Add at least one letter.")
        if not re.search(r"\d", password):
            raise ValidationError("Add at least one number.")
        if not re.search(r"[^A-Za-z0-9]", password):
            raise ValidationError("Add at least one symbol.")
        return password


class WorkspaceForm(StyledFormMixin, forms.Form):
    workspace_name = forms.CharField(
        max_length=160,
        label="Workspace name",
        widget=forms.TextInput(attrs={"placeholder": "Enter your workspace name"}),
    )
    workspace_slug = forms.SlugField(
        max_length=80,
        label="Workspace URL",
        validators=[validate_workspace_slug],
        widget=forms.TextInput(
            attrs={
                "placeholder": "your-workspace",
                "autocomplete": "off",
                "data-workspace-slug": "",
            }
        ),
    )
    logo = forms.FileField(
        required=False,
        label="Workspace logo (optional)",
        validators=[validate_workspace_logo],
        widget=forms.FileInput(
            attrs={"accept": ".png,.jpg,.jpeg,.svg,image/png,image/jpeg,image/svg+xml"}
        ),
    )
    timezone = forms.ChoiceField(
        choices=TIMEZONE_CHOICES,
        initial="Asia/Manila",
    )

    def __init__(self, *args, base_domain="localhost", tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_domain = base_domain
        self.tenant = tenant
        self.apply_widget_styles()
        self.fields["workspace_name"].widget.attrs["data-workspace-name"] = ""
        self.fields["workspace_slug"].widget.attrs.update(
            {
                "hx-get": reverse("onboarding:check_workspace_slug"),
                "hx-trigger": "keyup changed delay:350ms, blur",
                "hx-target": "#workspace-slug-feedback",
                "hx-include": "[name='workspace_slug']",
            }
        )

    def clean_workspace_slug(self):
        slug = self.cleaned_data["workspace_slug"].lower()
        hostname = f"{slug}.{self.base_domain}"
        tenants = Tenant.objects.filter(slug=slug)
        domains = TenantDomain.objects.filter(hostname=hostname)
        if self.tenant is not None:
            tenants = tenants.exclude(pk=self.tenant.pk)
            domains = domains.exclude(tenant=self.tenant)
        if tenants.exists() or domains.exists():
            raise ValidationError("That workspace URL is already taken.")
        return slug


class BusinessForm(StyledFormMixin, forms.Form):
    legal_name = forms.CharField(
        max_length=160,
        label="Business name",
        widget=forms.TextInput(
            attrs={"placeholder": "Enter your registered business name", "data-business-name": ""}
        ),
    )
    industry = forms.ChoiceField(
        label="Business industry",
        choices=(("", "Select your industry"), *Industry.choices),
        widget=forms.Select(attrs={"data-business-industry": ""}),
    )
    company_size = forms.ChoiceField(
        label="Business size",
        choices=(("", "Select your team size"), *CompanySize.choices),
        widget=forms.Select(attrs={"data-business-size": ""}),
    )
    currency = forms.ChoiceField(
        choices=Currency.choices,
        initial=Currency.PHP,
        widget=forms.Select(attrs={"data-business-currency": ""}),
    )
    timezone = forms.ChoiceField(
        choices=TIMEZONE_CHOICES,
        initial="Asia/Manila",
        widget=forms.Select(attrs={"data-business-timezone": ""}),
    )
    business_email = forms.EmailField(
        required=False,
        label="Business email (optional)",
        widget=forms.EmailInput(
            attrs={"placeholder": "admin@your-business.com", "autocomplete": "email"}
        ),
    )
    address = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Business address"}),
    )
    tax_identifier = forms.CharField(
        required=False,
        max_length=80,
        label="Tax identification number",
        widget=forms.TextInput(attrs={"placeholder": "Tax identification number"}),
    )
    registration_number = forms.CharField(
        required=False,
        max_length=80,
        widget=forms.TextInput(attrs={"placeholder": "Company registration number"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_widget_styles()


class SignInForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={"placeholder": "Enter your email address", "autocomplete": "email"}
        ),
    )
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(
            attrs={"placeholder": "Enter your password", "autocomplete": "current-password"}
        ),
    )

    def __init__(self, *args, request=None, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.tenant = tenant
        self.user = None
        self.apply_widget_styles()

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data
        self.user = authenticate(
            self.request,
            username=cleaned_data["email"].lower(),
            password=cleaned_data["password"],
        )
        if self.user is None:
            raise ValidationError("The email address or password is incorrect.")
        if self.tenant is not None and not TenantMembership.objects.filter(
            tenant=self.tenant,
            user=self.user,
            is_active=True,
        ).exists():
            self.user = None
            raise ValidationError("The email address or password is incorrect.")
        return cleaned_data

    def get_user(self):
        return self.user
