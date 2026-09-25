from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import MovementType, Product, ProductCustomValue, ProductEvent, ProductImage
from .product_services import generate_product_sku
from .services import change_stock, require_product_editor


@transaction.atomic
def apply_stock_action(*, product, kind, data, actor):
    require_product_editor(actor)
    if not product.track_inventory:
        raise ValidationError("Inventory tracking is disabled for this product.")
    location = data["location"]
    note = data.get("note", "")
    if kind == "receive":
        return change_stock(
            product=product,
            location=location,
            quantity_delta=data["quantity"],
            movement_type=MovementType.RECEIPT,
            actor=actor,
            note=note,
        )
    if kind == "adjust":
        return change_stock(
            product=product,
            location=location,
            quantity_delta=data["delta"],
            movement_type=MovementType.ADJUSTMENT,
            actor=actor,
            note=note,
        )
    if kind == "transfer":
        destination = data["destination"]
        if destination.pk == location.pk:
            raise ValidationError("Choose a different destination location.")
        # Lock both existing balances in a stable order before applying either movement.
        from .models import StockLevel

        list(
            StockLevel.objects.select_for_update()
            .filter(product=product, location__in=(location, destination))
            .order_by("location_id")
        )
        transfer_group = uuid4()
        reference = f"TR-{timezone.localdate().year}-{str(transfer_group)[:8].upper()}"
        change_stock(
            product=product,
            location=location,
            quantity_delta=-data["quantity"],
            movement_type=MovementType.TRANSFER,
            actor=actor,
            note=f"To {destination.name}. {note}".strip()[:240],
            reference=reference,
            counterparty_location=destination,
            transfer_group=transfer_group,
        )
        return change_stock(
            product=product,
            location=destination,
            quantity_delta=data["quantity"],
            movement_type=MovementType.TRANSFER,
            actor=actor,
            note=f"From {location.name}. {note}".strip()[:240],
            reference=reference,
            counterparty_location=location,
            transfer_group=transfer_group,
        )
    raise ValidationError("Unknown stock action.")


@transaction.atomic
def duplicate_product(*, source, actor):
    require_product_editor(actor)
    duplicate = Product(
        tenant=source.tenant,
        name=f"Copy of {source.name}"[:160],
        sku=generate_product_sku(),
        category=source.category,
        description=source.description,
        selling_price=source.selling_price,
        unit_cost=source.unit_cost,
        is_active=False,
        track_inventory=source.track_inventory,
        unit_of_measure=source.unit_of_measure,
        has_variants=source.has_variants,
        brand=source.brand,
        model=source.model,
        created_by=actor,
        updated_by=actor,
    )
    duplicate.save()
    for value in ProductCustomValue.objects.filter(product=source):
        ProductCustomValue.objects.create(product=duplicate, field=value.field, value=value.value)
    ProductEvent.objects.create(
        product=duplicate, actor=actor, description=f"Duplicated from {source.sku}"
    )
    return duplicate


@transaction.atomic
def set_product_archived(*, product, archived, actor):
    require_product_editor(actor)
    product.is_active = not archived
    product.updated_by = actor
    product.save(update_fields=("is_active", "updated_by", "updated_at"))
    ProductEvent.objects.create(
        product=product,
        actor=actor,
        description="Archived product" if archived else "Reactivated product",
    )
    return product


@transaction.atomic
def add_gallery_image(*, product, image, alt_text, actor):
    require_product_editor(actor)
    if ProductImage.objects.filter(product=product).count() >= 8:
        raise ValidationError("A product can have up to eight additional images.")
    photo = ProductImage(product=product, image=image, alt_text=alt_text, tenant=product.tenant)
    photo.save()
    ProductEvent.objects.create(product=product, actor=actor, description="Added product image")
    return photo
