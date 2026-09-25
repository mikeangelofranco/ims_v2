from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.dashboard.selectors import get_dashboard_snapshot
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Tenant, TenantMembership, TenantRole

from ..models import Location, MovementType, Product, StockLevel
from ..services import change_stock

User = get_user_model()


@pytest.mark.django_db
def test_dashboard_snapshot_aggregates_tenant_inventory():
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    with tenant_context(tenant):
        location = Location.objects.create(name="Main Warehouse", code="main", is_default=True)
        healthy = Product.objects.create(name="Healthy", sku="OK-1", unit_cost=Decimal("10"))
        low = Product.objects.create(name="Low", sku="LOW-1", unit_cost=Decimal("20"))
        empty = Product.objects.create(name="Empty", sku="OUT-1", unit_cost=Decimal("30"))
        StockLevel.objects.create(
            product=healthy, location=location, quantity=10, minimum_quantity=5
        )
        StockLevel.objects.create(product=low, location=location, quantity=2, minimum_quantity=5)
        StockLevel.objects.create(product=empty, location=location, quantity=0, minimum_quantity=5)

        snapshot = get_dashboard_snapshot()

    assert snapshot.total_products == 3
    assert snapshot.in_stock_count == 1
    assert snapshot.low_stock_count == 1
    assert snapshot.out_of_stock_count == 1
    assert snapshot.inventory_value == Decimal("140")
    assert snapshot.stock_health == 33
    assert snapshot.low_stock_items[0].product == low


@pytest.mark.django_db
def test_stock_change_locks_balance_and_records_movement():
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    user = User.objects.create_user(email="owner@acme.example", password="StrongPass1!")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    with tenant_context(tenant):
        location = Location.objects.create(name="Main Warehouse", code="main")
        product = Product.objects.create(name="Cable", sku="CBL-1")

        movement = change_stock(
            product=product,
            location=location,
            quantity_delta=12,
            movement_type=MovementType.RECEIPT,
            actor=user,
        )

        assert StockLevel.objects.get(product=product, location=location).quantity == 12
        assert movement.balance_after == 12
        with pytest.raises(ValidationError, match="negative"):
            change_stock(
                product=product,
                location=location,
                quantity_delta=-13,
                movement_type=MovementType.ISSUE,
                actor=user,
            )


@pytest.mark.django_db
def test_inventory_relationships_reject_cross_tenant_records():
    first = Tenant.objects.create(name="First", slug="first")
    second = Tenant.objects.create(name="Second", slug="second")
    with tenant_context(first):
        product = Product.objects.create(name="Cable", sku="CBL-1")
    with tenant_context(second):
        location = Location.objects.create(name="Second Warehouse", code="second")
        with pytest.raises(ValidationError, match="same workspace"):
            StockLevel.objects.create(product=product, location=location, quantity=1)


@pytest.mark.django_db
def test_products_normalize_blank_barcodes_without_false_uniqueness_conflicts():
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    with tenant_context(tenant):
        first = Product.objects.create(name="First", sku="FIRST", barcode="")
        second = Product.objects.create(name="Second", sku="SECOND", barcode="  ")

    assert first.barcode is None
    assert second.barcode is None
