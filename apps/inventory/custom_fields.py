from django.core.exceptions import ValidationError
from django.db import models

from apps.tenancy.models import TenantOwnedModel


class ProductCustomField(TenantOwnedModel):
    name = models.CharField(max_length=80)
    key = models.SlugField(max_length=80)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("created_at", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "key"),
                name="inventory_custom_field_tenant_key_uniq",
            )
        ]

    def __str__(self):
        return self.name


class ProductCustomValue(TenantOwnedModel):
    product = models.ForeignKey(
        "inventory.Product", on_delete=models.CASCADE, related_name="custom_values"
    )
    field = models.ForeignKey(
        ProductCustomField, on_delete=models.PROTECT, related_name="product_values"
    )
    value = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "product", "field"),
                name="inventory_custom_value_tenant_product_field_uniq",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.product_id and self.product.tenant_id != self.tenant_id:
            errors["product"] = "Product must belong to the same workspace."
        if self.field_id and self.field.tenant_id != self.tenant_id:
            errors["field"] = "Custom field must belong to the same workspace."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
