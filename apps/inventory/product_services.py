from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.text import slugify

from apps.tenancy.context import get_current_tenant
from apps.tenancy.models import Tenant, TenantMembership, TenantRole

from .models import Category, Location, Product, ProductCustomField, ProductCustomValue


def generate_product_sku():
    for _ in range(5):
        sku = f"PRD-{uuid4().hex[:12].upper()}"
        if not Product.objects.filter(sku=sku).exists():
            return sku
    raise ValidationError("Unable to generate SKU. Enter one manually.")


def generate_category_code():
    tenant = get_current_tenant()
    Tenant.objects.select_for_update().get(pk=tenant.pk)
    existing = set(Category.objects.values_list("code", flat=True))
    for number in range(1, 100000):
        code = f"CAT-{number:03d}"
        if code not in existing:
            return code
    raise ValidationError("Unable to generate a category code.")


def opening_stock_location():
    # Serialize default-location provisioning for a new workspace.
    tenant = get_current_tenant()
    Tenant.objects.select_for_update().get(pk=tenant.pk)
    locations = Location.objects.filter(is_active=True)
    location = locations.filter(is_default=True).first()
    if location:
        return location
    if locations.count() == 1:
        return locations.first()
    if locations.exists():
        raise ValidationError("Choose the location for opening stock.")
    return Location.objects.create(
        name="Main Warehouse",
        code=f"main-{uuid4().hex[:8]}",
        is_default=not Location.objects.filter(is_default=True).exists(),
    )


def save_custom_values(*, product, form):
    for definition in form.custom_definitions:
        key = f"custom_{definition.key}"
        value = form.cleaned_data.get(key, "")
        if value or product.custom_values.filter(field=definition).exists():
            ProductCustomValue.objects.update_or_create(
                product=product,
                field=definition,
                defaults={"value": value},
            )


def require_custom_field_admin(actor):
    if not TenantMembership.objects.filter(
        tenant=get_current_tenant(),
        user=actor,
        is_active=True,
        role__in=(TenantRole.OWNER, TenantRole.ADMIN),
    ).exists():
        raise PermissionDenied("Only owners and administrators can manage custom fields.")


@transaction.atomic
def create_category(
    *, name, actor, code="", description="", icon="folder", is_active=True
):
    from .services import require_product_editor

    require_product_editor(actor)
    category = Category(
        name=name,
        slug=slugify(name)[:120] or f"category-{uuid4().hex[:12]}",
        code=code or generate_category_code(),
        description=description,
        icon=icon,
        is_active=is_active,
        created_by=actor,
        updated_by=actor,
        tenant=get_current_tenant(),
    )
    category.full_clean()
    category.save()
    return category


@transaction.atomic
def update_category(*, category, data, actor):
    from .services import require_product_editor

    require_product_editor(actor)
    if category.tenant_id != get_current_tenant().pk:
        raise PermissionDenied("Category must belong to the current workspace.")
    category.name = data["name"]
    category.slug = slugify(data["name"])[:120] or category.slug
    category.code = data.get("code") or category.code or generate_category_code()
    category.description = data.get("description", "")
    category.icon = data.get("icon", "folder")
    category.is_active = data.get("is_active", True)
    category.updated_by = actor
    category.save()
    return category


@transaction.atomic
def set_category_active(*, category, is_active, actor):
    from .services import require_product_editor

    require_product_editor(actor)
    if category.tenant_id != get_current_tenant().pk:
        raise PermissionDenied("Category must belong to the current workspace.")
    category.is_active = is_active
    category.updated_by = actor
    category.save(update_fields=("is_active", "updated_by", "updated_at"))
    return category


@transaction.atomic
def create_custom_field(*, name, actor):
    require_custom_field_admin(actor)
    definition = ProductCustomField(
        name=name,
        key=slugify(name)[:80] or f"field-{uuid4().hex[:12]}",
        tenant=get_current_tenant(),
    )
    definition.full_clean()
    definition.save()
    return definition


@transaction.atomic
def set_custom_field_active(*, definition, is_active, actor):
    require_custom_field_admin(actor)
    if definition.tenant_id != get_current_tenant().pk:
        raise PermissionDenied("Custom field must belong to the current workspace.")
    definition.is_active = is_active
    definition.save(update_fields=("is_active", "updated_at"))
    return definition
