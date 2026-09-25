import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from apps.tenancy.context import tenant_context
from apps.tenancy.models import TenantDomain, TenantMembership, TenantRole

from ..models import Location, MovementType, Product, StockLevel, StockMovement
from ..services import change_stock

pytestmark = pytest.mark.django_db


@override_settings(ALLOWED_HOSTS=["acme.localhost", "other.localhost"])
def test_movement_page_filters_summaries_and_tenant_boundary(workspace):
    tenant, user, _, foreign, _, main = workspace
    with tenant_context(tenant):
        product = Product.objects.get(sku="Healthy")
        movement = change_stock(
            product=product,
            location=main,
            quantity_delta=7,
            movement_type=MovementType.RECEIPT,
            actor=user,
            note="Supplier receipt",
        )
    foreign_user = get_user_model().objects.create_user(email="other@example.com")
    TenantMembership.objects.create(
        tenant=foreign.tenant, user=foreign_user, role=TenantRole.OWNER
    )
    TenantDomain.objects.create(tenant=foreign.tenant, hostname="other.localhost")
    with tenant_context(foreign.tenant):
        foreign_location = Location.objects.create(name="Foreign warehouse", code="warehouse")
        foreign_stock = StockLevel.objects.create(product=foreign, location=foreign_location)
        foreign_movement = change_stock(
            product=foreign,
            location=foreign_location,
            quantity_delta=3,
            movement_type=MovementType.RECEIPT,
            actor=foreign_user,
            note="Private shipment",
        )
        assert foreign_stock.quantity == 0

    client = Client()
    client.force_login(user)
    url = reverse("inventory:movement_list")
    response = client.get(url, HTTP_HOST="acme.localhost")
    assert response.status_code == 200
    assert response.context["summary"]["receipt"] == {
        "quantity": 7,
        "transactions": 1,
    }
    assert movement.reference.encode() in response.content
    assert b"Supplier receipt" in response.content
    assert b'movement-mobile__stats' in response.content
    assert b'movement-mobile__feed' in response.content
    assert b'aria-current="page"' in response.content
    assert b"Stock Movement" in response.content
    assert foreign_movement.reference.encode() not in response.content
    assert b"Private shipment" not in response.content
    filtered = client.get(url, {"q": product.sku}, HTTP_HOST="acme.localhost")
    assert filtered.context["page_obj"].paginator.count == 1
    empty = client.get(url, {"q": "Private shipment"}, HTTP_HOST="acme.localhost")
    assert empty.context["page_obj"].paginator.count == 0


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_page_actions_create_tenant_scoped_movements_and_collapse_transfer(workspace):
    tenant, user, membership, foreign, _, main = workspace
    with tenant_context(tenant):
        product = Product.objects.get(sku="Healthy")
        branch = Location.objects.create(name="Branch", code="branch")
    with tenant_context(foreign.tenant):
        foreign_location = Location.objects.create(name="Foreign", code="foreign-location")
    client = Client()
    client.force_login(user)
    url = reverse("inventory:movement_list")

    response = client.post(
        url,
        {
            "action": "receive",
            "product": product.pk,
            "location": main.pk,
            "quantity": 5,
            "note": "Delivery",
        },
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 302
    response = client.post(
        url,
        {
            "action": "transfer",
            "product": product.pk,
            "location": main.pk,
            "destination": branch.pk,
            "quantity": 4,
        },
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 302
    with tenant_context(tenant):
        transfers = StockMovement.objects.filter(movement_type=MovementType.TRANSFER)
        assert transfers.count() == 2
        assert transfers.values("reference").distinct().count() == 1
        assert transfers.values("transfer_group").distinct().count() == 1
        assert StockLevel.objects.get(product=product, location=main).quantity == 21
        assert StockLevel.objects.get(product=product, location=branch).quantity == 4
    response = client.get(url, HTTP_HOST="acme.localhost")
    assert response.context["summary"]["transfer"] == {
        "quantity": 4,
        "transactions": 1,
    }
    assert response.context["page_obj"].paginator.count == 2

    rejected = client.post(
        url,
        {
            "action": "receive",
            "product": foreign.pk,
            "location": foreign_location.pk,
            "quantity": 5,
        },
        HTTP_HOST="acme.localhost",
    )
    assert rejected.status_code == 400
    assert "product" in rejected.context["action_form"].errors
    membership.role = TenantRole.VIEWER
    membership.save()
    forbidden = client.post(
        url,
        {
            "action": "receive",
            "product": product.pk,
            "location": main.pk,
            "quantity": 1,
        },
        HTTP_HOST="acme.localhost",
    )
    assert forbidden.status_code == 403


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_movement_export_uses_current_tenant_and_filters(workspace):
    tenant, user, _, _, _, main = workspace
    with tenant_context(tenant):
        product = Product.objects.get(sku="Healthy")
        movement = change_stock(
            product=product,
            location=main,
            quantity_delta=-2,
            movement_type=MovementType.ADJUSTMENT,
            actor=user,
            note="Stock count",
        )
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("inventory:movement_export"),
        {"type": "adjustment", "q": movement.reference},
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert movement.reference.encode() in response.content
    assert b"Stock count" in response.content
