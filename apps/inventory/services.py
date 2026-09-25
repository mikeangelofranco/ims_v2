from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenancy.context import get_current_tenant
from apps.tenancy.models import TenantMembership

from .models import MovementType, Product, ProductEvent, StockLevel, StockMovement


@transaction.atomic
def change_stock(
    *, product, location, quantity_delta, movement_type, actor, note="",
    reference="", counterparty_location=None, transfer_group=None
):
    if not product.track_inventory:
        raise ValidationError("Inventory tracking is disabled for this product.")
    if quantity_delta == 0:
        raise ValidationError("Stock changes must have a non-zero quantity.")
    if movement_type == MovementType.RECEIPT and quantity_delta < 0:
        raise ValidationError("A stock receipt must increase quantity.")
    if movement_type == MovementType.ISSUE and quantity_delta > 0:
        raise ValidationError("A stock issue must decrease quantity.")
    if product.tenant_id != get_current_tenant().pk or location.tenant_id != product.tenant_id:
        raise ValidationError("Product and location must belong to the current workspace.")
    require_product_editor(actor)

    stock, _ = StockLevel.objects.select_for_update().get_or_create(
        product=product,
        location=location,
        defaults={"quantity": 0},
    )
    new_balance = stock.quantity + quantity_delta
    if new_balance < 0:
        raise ValidationError("This movement would make stock negative.")
    stock.quantity = new_balance
    stock.save(update_fields=["quantity", "updated_at"])
    movement = StockMovement.objects.create(
        product=product,
        location=location,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        balance_after=new_balance,
        actor=actor,
        note=note.strip(),
        reference=reference,
        counterparty_location=counterparty_location,
        transfer_group=transfer_group,
    )
    action = {
        MovementType.RECEIPT: "Received",
        MovementType.ISSUE: "Issued",
        MovementType.ADJUSTMENT: "Adjusted",
        MovementType.TRANSFER: "Transferred",
    }[movement_type]
    ProductEvent.objects.create(
        product=product,
        actor=actor,
        description=f"{action} {abs(quantity_delta)} {product.unit_of_measure} "
        f"{'to' if quantity_delta > 0 else 'from'} {location.name}",
    )
    return movement


def require_product_editor(actor):
    from django.core.exceptions import PermissionDenied

    from apps.tenancy.context import get_current_tenant
    from apps.tenancy.models import TenantRole

    if not TenantMembership.objects.filter(
        tenant=get_current_tenant(),
        user=actor,
        is_active=True,
        role__in=(TenantRole.OWNER, TenantRole.ADMIN, TenantRole.MEMBER),
    ).exists():
        raise PermissionDenied("Your workspace role cannot change products.")


@transaction.atomic
def save_product(*, form, actor, opening_stock=None):
    require_product_editor(actor)
    product = form.save(commit=False)
    previous = Product.objects.filter(pk=product.pk).first() if product.pk else None
    if (
        opening_stock
        and not product.track_inventory
        and (opening_stock.get("quantity") or opening_stock.get("minimum_quantity"))
    ):
        raise ValidationError("Opening stock requires inventory tracking.")
    product.updated_by = actor
    if previous is None:
        product.created_by = actor
    product.save()
    from .product_services import opening_stock_location, save_custom_values

    save_custom_values(product=product, form=form)
    if previous is None:
        ProductEvent.objects.create(product=product, actor=actor, description="Created product")
    elif form.has_changed():
        if previous.selling_price != product.selling_price:
            ProductEvent.objects.create(
                product=product,
                actor=actor,
                description=f"Changed selling price from {previous.selling_price:,.2f} "
                f"to {product.selling_price:,.2f}",
            )
        if "image" in form.changed_data:
            ProductEvent.objects.create(
                product=product, actor=actor, description="Updated product image"
            )
        if any(name not in {"selling_price", "image"} for name in form.changed_data):
            ProductEvent.objects.create(
                product=product, actor=actor, description="Updated product information"
            )
    if opening_stock and product.track_inventory:
        location = opening_stock.get("location") or opening_stock_location()
        StockLevel.objects.create(
            product=product,
            location=location,
            minimum_quantity=opening_stock["minimum_quantity"],
        )
        if opening_stock["quantity"]:
            change_stock(
                product=product,
                location=location,
                quantity_delta=opening_stock["quantity"],
                movement_type=MovementType.RECEIPT,
                actor=actor,
                note="Opening stock",
            )
    return product
