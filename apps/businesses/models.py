from django.db import models

from apps.tenancy.models import Tenant, TenantOwnedModel


class Industry(models.TextChoices):
    RETAIL = "retail", "Retail"
    WHOLESALE = "wholesale", "Trading / Wholesale"
    MANUFACTURING = "manufacturing", "Manufacturing"
    SERVICES = "services", "Professional services"
    OTHER = "other", "Other"


class CompanySize(models.TextChoices):
    SOLO = "solo", "Just me"
    SMALL = "2-10", "2 – 10 employees"
    MEDIUM = "11-50", "11 – 50 employees"
    LARGE = "51+", "51+ employees"


class Currency(models.TextChoices):
    PHP = "PHP", "Philippine Peso (PHP)"
    USD = "USD", "US Dollar (USD)"
    SGD = "SGD", "Singapore Dollar (SGD)"
    JPY = "JPY", "Japanese Yen (JPY)"
    EUR = "EUR", "Euro (EUR)"
    GBP = "GBP", "British Pound (GBP)"


class BusinessProfile(TenantOwnedModel):
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.PROTECT,
        related_name="business_profile",
    )
    legal_name = models.CharField(max_length=160)
    industry = models.CharField(max_length=32, choices=Industry.choices)
    company_size = models.CharField(max_length=16, choices=CompanySize.choices)
    country = models.CharField(max_length=2, default="PH")
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.PHP)
    business_email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    tax_identifier = models.CharField(max_length=80, blank=True)
    registration_number = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ("legal_name",)

    def __str__(self):
        return self.legal_name
