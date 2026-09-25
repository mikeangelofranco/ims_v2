from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.tenancy.models import TenantOwnedModel

from .custom_fields import ProductCustomField, ProductCustomValue  # noqa: F401
from .validators import validate_product_image


class Category(TenantOwnedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120)
    code = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=240, blank=True)
    icon = models.CharField(max_length=40, default="folder")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_inventory_categories",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_inventory_categories",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "slug"), name="inventory_category_tenant_slug_uniq"
            ),
            models.UniqueConstraint(
                fields=("tenant", "code"), name="inventory_category_tenant_code_uniq"
            ),
        ]

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.code = (self.code or "").strip().upper()
        if not self.code and self._state.adding:
            self.code = f"CAT-{str(self.pk)[:8].upper()}"
        if not self.name:
            raise ValidationError({"name": "Category name cannot be blank."})
        if not self.code:
            raise ValidationError({"code": "Category code cannot be blank."})
        if self.tenant_id:
            from apps.tenancy.models import TenantMembership

            for field_name in ("created_by", "updated_by"):
                user_id = getattr(self, f"{field_name}_id")
                if user_id and not TenantMembership.objects.filter(
                    tenant_id=self.tenant_id, user_id=user_id, is_active=True
                ).exists():
                    raise ValidationError(
                        {field_name: "User must belong to the same workspace."}
                    )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Location(TenantOwnedModel):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=40)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "code"), name="inventory_location_tenant_code_uniq"
            ),
            models.UniqueConstraint(
                fields=("tenant",),
                condition=models.Q(is_default=True),
                name="inventory_one_default_location_per_tenant",
            ),
        ]

    def __str__(self):
        return self.name


class UnitOfMeasure(models.TextChoices):
    PIECE = "pcs", "Pieces (pcs)"
    BOX = "box", "Box"
    PACK = "pack", "Pack"
    SET = "set", "Set"
    KILOGRAM = "kg", "Kilogram (kg)"
    LITER = "liter", "Liter"
    METER = "meter", "Meter"


class Product(TenantOwnedModel):
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=80)
    barcode = models.CharField(max_length=80, blank=True, null=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        blank=True,
        null=True,
    )
    image = models.FileField(
        upload_to="product-images/%Y/%m/", blank=True, validators=[validate_product_image]
    )
    description = models.CharField(max_length=500, blank=True)
    selling_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_products",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_products",
        null=True,
        blank=True,
    )
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    track_inventory = models.BooleanField(default=True)
    unit_of_measure = models.CharField(
        max_length=16, choices=UnitOfMeasure, default=UnitOfMeasure.PIECE
    )
    has_variants = models.BooleanField(default=False)
    brand = models.CharField(max_length=120, blank=True)
    model = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "sku"), name="inventory_product_tenant_sku_uniq"
            ),
            models.UniqueConstraint(
                fields=("tenant", "barcode"),
                condition=models.Q(barcode__isnull=False),
                name="inventory_product_tenant_barcode_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(selling_price__gte=0),
                name="inventory_product_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0), name="inventory_product_cost_nonnegative"
            ),
        ]

    def clean(self):
        super().clean()
        self.sku = self.sku.strip()
        if not self.sku:
            raise ValidationError({"sku": "SKU cannot be blank."})
        if self.barcode is not None:
            self.barcode = self.barcode.strip() or None
        if self.category_id and self.category.tenant_id != self.tenant_id:
            raise ValidationError({"category": "Category must belong to the same workspace."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.sku})"


class StockLevel(TenantOwnedModel):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_levels")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="stock_levels")
    quantity = models.PositiveIntegerField(default=0)
    minimum_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("product__name", "location__name")
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "product", "location"),
                name="inventory_stock_tenant_product_location_uniq",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.product_id and not self.product.track_inventory:
            errors["product"] = "Inventory tracking is disabled for this product."
        if self.product_id and self.product.tenant_id != self.tenant_id:
            errors["product"] = "Product must belong to the same workspace."
        if self.location_id and self.location.tenant_id != self.tenant_id:
            errors["location"] = "Location must belong to the same workspace."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class MovementType(models.TextChoices):
    RECEIPT = "receipt", "Received stock"
    ISSUE = "issue", "Issued stock"
    ADJUSTMENT = "adjustment", "Adjusted stock"
    TRANSFER = "transfer", "Transferred stock"


class StockMovement(TenantOwnedModel):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=16, choices=MovementType.choices)
    quantity_delta = models.IntegerField()
    balance_after = models.PositiveIntegerField()
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="inventory_movements",
        blank=True,
        null=True,
    )
    note = models.CharField(max_length=240, blank=True)
    reference = models.CharField(max_length=40, blank=True)
    counterparty_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="counterparty_movements",
        blank=True,
        null=True,
    )
    transfer_group = models.UUIDField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity_delta=0),
                name="inventory_movement_delta_nonzero",
            ),
            models.UniqueConstraint(
                fields=("tenant", "reference", "location"),
                name="inventory_movement_tenant_reference_uniq",
            ),
        ]
        indexes = [models.Index(fields=("tenant", "-created_at"))]

    def clean(self):
        super().clean()
        errors = {}
        if self.product_id and self.product.tenant_id != self.tenant_id:
            errors["product"] = "Product must belong to the same workspace."
        if self.location_id and self.location.tenant_id != self.tenant_id:
            errors["location"] = "Location must belong to the same workspace."
        if (
            self.counterparty_location_id
            and self.counterparty_location.tenant_id != self.tenant_id
        ):
            errors["counterparty_location"] = (
                "Counterparty location must belong to the same workspace."
            )
        if self.actor_id and self.tenant_id:
            from apps.tenancy.models import TenantMembership

            if not TenantMembership.objects.filter(
                tenant_id=self.tenant_id, user_id=self.actor_id, is_active=True
            ).exists():
                errors["actor"] = "Actor must belong to the same workspace."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.reference:
            prefix = {
                MovementType.RECEIPT: "GR",
                MovementType.ISSUE: "SO",
                MovementType.ADJUSTMENT: "ADJ",
                MovementType.TRANSFER: "TR",
            }.get(self.movement_type, "MV")
            self.reference = f"{prefix}-{timezone.localdate().year}-{str(self.pk)[:8].upper()}"
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def display_reference(self):
        return self.reference


class ProductImage(TenantOwnedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="gallery_images")
    image = models.FileField(upload_to="product-images/%Y/%m/", validators=[validate_product_image])
    alt_text = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ("created_at", "pk")

    def clean(self):
        super().clean()
        if self.product_id and self.product.tenant_id != self.tenant_id:
            raise ValidationError({"product": "Product must belong to the same workspace."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ProductEvent(TenantOwnedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="activity_events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="product_events",
        null=True,
        blank=True,
    )
    description = models.CharField(max_length=240)

    class Meta:
        ordering = ("-created_at", "-pk")
        indexes = [models.Index(fields=("tenant", "product", "-created_at"))]

    def clean(self):
        super().clean()
        errors = {}
        if self.product_id and self.product.tenant_id != self.tenant_id:
            errors["product"] = "Product must belong to the same workspace."
        if self.actor_id and self.tenant_id:
            from apps.tenancy.models import TenantMembership

            if not TenantMembership.objects.filter(
                tenant_id=self.tenant_id, user_id=self.actor_id, is_active=True
            ).exists():
                errors["actor"] = "Actor must belong to the same workspace."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
