from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.tenancy.context import tenant_context
from apps.tenancy.models import TenantMembership, TenantRole

from ..models import (
    Location,
    Product,
    ProductCustomField,
    ProductCustomValue,
    ProductEvent,
    ProductImage,
    StockLevel,
    StockMovement,
)
from ..services import change_stock

pytestmark = pytest.mark.django_db


@override_settings(ALLOWED_HOSTS=["acme.localhost", "other.localhost"])
def test_product_detail_and_search_links_respect_workspace(workspace):
    tenant, user, membership, foreign, _, _ = workspace
    with tenant_context(tenant):
        product = Product.objects.get(sku="Healthy")
        product.brand = "TWS"
        product.model = "EarBuds Pro"
        product.description = "Stereo earbuds"
        product.selling_price = Decimal("1299.00")
        product.unit_cost = Decimal("850.00")
        product.save()
        field = ProductCustomField.objects.create(name="Warranty", key="warranty")
        ProductCustomValue.objects.create(product=product, field=field, value="1 Year")
    client = Client()
    client.force_login(user)
    url = reverse("inventory:product_detail", args=[product.pk])
    response = client.get(url, HTTP_HOST="acme.localhost")
    assert response.status_code == 200
    assert response.context["total_stock"] == 20
    assert response.context["minimum_stock"] == 5
    for value in (b"EarBuds Pro", b"Stereo earbuds", b"1 Year", b"1,299", b"850"):
        assert value in response.content
    assert b"Foreign secret" not in response.content
    assert b"No stock movements recorded." in response.content
    search = client.get(
        reverse("inventory:product_list"), {"q": "Healthy"}, HTTP_HOST="acme.localhost"
    )
    assert f'href="{url}"'.encode() in search.content
    assert (
        client.get(
            reverse("inventory:product_detail", args=[foreign.pk]), HTTP_HOST="acme.localhost"
        ).status_code
        == 404
    )
    membership.role = TenantRole.VIEWER
    membership.save()
    response = client.get(url, HTTP_HOST="acme.localhost")
    assert response.status_code == 200
    assert b"Receive Stock" not in response.content
    assert (
        client.post(
            reverse("inventory:product_stock_action", args=[product.pk, "receive"]),
            HTTP_HOST="acme.localhost",
        ).status_code
        == 403
    )


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_stock_actions_update_ledger_summary_and_activity(workspace):
    tenant, user, _, foreign, _, main = workspace
    with tenant_context(tenant):
        product = Product.objects.get(sku="Healthy")
        branch = Location.objects.create(name="Branch Office", code="branch")
        with pytest.raises(ValidationError, match="same workspace"):
            ProductEvent.objects.create(product=foreign, actor=user, description="Wrong tenant")
    with tenant_context(foreign.tenant):
        foreign_location = Location.objects.create(name="Foreign", code="foreign")
    client = Client()
    client.force_login(user)

    def stock_url(kind):
        return reverse("inventory:product_stock_action", args=[product.pk, kind])

    for kind, data in (
        ("receive", {"location": main.pk, "quantity": "5", "note": "Delivery"}),
        ("adjust", {"location": main.pk, "delta": "-1", "note": "Count"}),
        ("transfer", {"location": main.pk, "destination": branch.pk, "quantity": "4"}),
    ):
        assert client.post(stock_url(kind), data, HTTP_HOST="acme.localhost").status_code == 302
    with tenant_context(tenant):
        assert StockLevel.objects.get(product=product, location=main).quantity == 20
        assert StockLevel.objects.get(product=product, location=branch).quantity == 4
        assert StockMovement.objects.filter(product=product).count() == 4
        assert ProductEvent.objects.filter(product=product).count() == 4
    response = client.get(
        reverse("inventory:product_detail", args=[product.pk]), HTTP_HOST="acme.localhost"
    )
    assert response.context["total_stock"] == 24
    assert response.context["received_30d"] == 5
    assert response.context["adjusted_30d"] == -1
    assert response.context["issued_30d"] == 0
    assert b"Branch Office" in response.content
    assert b"Transferred" in response.content
    with tenant_context(tenant):
        old = StockMovement.objects.filter(product=product, movement_type="receipt").first()
        StockMovement.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=31)
        )
    response = client.get(
        reverse("inventory:product_detail", args=[product.pk]), HTTP_HOST="acme.localhost"
    )
    assert response.context["received_30d"] == 0
    response = client.post(
        stock_url("transfer"),
        {"location": main.pk, "destination": branch.pk, "quantity": "99"},
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 200
    with tenant_context(tenant):
        assert StockLevel.objects.get(product=product, location=main).quantity == 20
        assert StockLevel.objects.get(product=product, location=branch).quantity == 4
        assert StockMovement.objects.filter(product=product).count() == 4
    response = client.post(
        stock_url("receive"), {"location": "invalid", "quantity": "5"}, HTTP_HOST="acme.localhost"
    )
    assert (
        response.status_code == 200
        and "location" in response.context["stock_actions"][0]["form"].errors
    )
    response = client.post(
        stock_url("receive"),
        {"location": foreign_location.pk, "quantity": "5"},
        HTTP_HOST="acme.localhost",
    )
    assert "location" in response.context["stock_actions"][0]["form"].errors


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_duplicate_archive_label_and_gallery_are_real_and_tenant_scoped(workspace, tmp_path):
    tenant, user, _, foreign, _, location = workspace
    with tenant_context(tenant):
        source = Product.objects.get(sku="Healthy")
        source.selling_price = Decimal("555.00")
        source.save()
        field = ProductCustomField.objects.create(name="Warranty", key="warranty")
        ProductCustomValue.objects.create(product=source, field=field, value="2 years")
    client = Client(enforce_csrf_checks=False)
    client.force_login(user)
    with override_settings(MEDIA_ROOT=tmp_path):
        upload_url = reverse("inventory:product_gallery_upload", args=[source.pk])
        image = SimpleUploadedFile(
            "other.png", b"\x89PNG\r\n\x1a\npreview", content_type="image/png"
        )
        assert (
            client.post(
                upload_url, {"image": image, "alt_text": "Side view"}, HTTP_HOST="acme.localhost"
            ).status_code
            == 302
        )
        with tenant_context(tenant):
            photo = ProductImage.objects.get(product=source)
            assert photo.alt_text == "Side view"
        image_url = reverse("inventory:product_gallery_image", args=[source.pk, photo.pk])
        assert client.get(image_url, HTTP_HOST="acme.localhost").status_code == 200
        assert (
            client.get(
                reverse("inventory:product_gallery_image", args=[foreign.pk, photo.pk]),
                HTTP_HOST="acme.localhost",
            ).status_code
            == 404
        )
        invalid = SimpleUploadedFile("unsafe.svg", b"<svg></svg>", content_type="image/svg+xml")
        response = client.post(upload_url, {"image": invalid}, HTTP_HOST="acme.localhost")
        assert response.status_code == 200
    assert (
        client.get(
            reverse("inventory:product_label", args=[source.pk]), HTTP_HOST="acme.localhost"
        ).status_code
        == 200
    )
    response = client.post(
        reverse("inventory:product_duplicate", args=[source.pk]), HTTP_HOST="acme.localhost"
    )
    assert response.status_code == 302
    with tenant_context(tenant):
        duplicate = Product.objects.get(name="Copy of Healthy")
        assert not duplicate.is_active
        assert duplicate.sku != source.sku and duplicate.barcode is None
        assert duplicate.selling_price == Decimal("555.00")
        assert not StockLevel.objects.filter(product=duplicate).exists()
        assert ProductCustomValue.objects.get(product=duplicate, field=field).value == "2 years"
    archive_url = reverse("inventory:product_archive", args=[source.pk])
    client.post(archive_url, HTTP_HOST="acme.localhost")
    with tenant_context(tenant):
        assert not Product.objects.get(pk=source.pk).is_active
    client.post(archive_url, HTTP_HOST="acme.localhost")
    with tenant_context(tenant):
        assert Product.objects.get(pk=source.pk).is_active


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_every_product_detail_endpoint_rejects_foreign_product(workspace):
    tenant, user, _, foreign, _, _ = workspace
    client = Client()
    client.force_login(user)
    foreign_urls = (
        ("get", reverse("inventory:product_detail", args=[foreign.pk])),
        ("get", reverse("inventory:product_label", args=[foreign.pk])),
        ("get", reverse("inventory:product_image", args=[foreign.pk])),
        ("get", reverse("inventory:product_gallery_image", args=[foreign.pk, foreign.pk])),
        ("get", reverse("inventory:product_edit", args=[foreign.pk])),
        ("post", reverse("inventory:product_stock_action", args=[foreign.pk, "receive"])),
        ("post", reverse("inventory:product_duplicate", args=[foreign.pk])),
        ("post", reverse("inventory:product_archive", args=[foreign.pk])),
        ("post", reverse("inventory:product_gallery_upload", args=[foreign.pk])),
    )
    for method, url in foreign_urls:
        response = getattr(client, method)(url, HTTP_HOST="acme.localhost")
        assert response.status_code == 404, url
    with tenant_context(tenant):
        assert not Product.objects.filter(pk=foreign.pk).exists()
    with tenant_context(foreign.tenant):
        assert Product.objects.get(pk=foreign.pk).is_active


def test_stock_service_requires_editor_and_movement_actor_membership(workspace):
    tenant, user, membership, foreign, _, location = workspace
    with tenant_context(foreign.tenant):
        foreign_location = Location.objects.create(name="Other Warehouse", code="other")
    with tenant_context(tenant):
        product = Product.objects.get(sku="Healthy")
        before = StockLevel.objects.get(product=product, location=location).quantity
        membership.role = TenantRole.VIEWER
        membership.save()
        with pytest.raises(PermissionDenied):
            change_stock(
                product=product,
                location=location,
                quantity_delta=1,
                movement_type="receipt",
                actor=user,
            )
        with pytest.raises(ValidationError, match="current workspace"):
            change_stock(
                product=foreign,
                location=location,
                quantity_delta=1,
                movement_type="receipt",
                actor=user,
            )
        with pytest.raises(ValidationError, match="current workspace"):
            change_stock(
                product=product,
                location=foreign_location,
                quantity_delta=1,
                movement_type="receipt",
                actor=user,
            )
        assert StockLevel.objects.get(product=product, location=location).quantity == before
        assert not StockMovement.objects.filter(product=product).exists()
    foreign_user = get_user_model().objects.create_user(email="other@example.com", password="pass")
    TenantMembership.objects.create(tenant=foreign.tenant, user=foreign_user)
    with tenant_context(tenant):
        with pytest.raises(ValidationError, match="same workspace"):
            StockMovement.objects.create(
                product=product,
                location=location,
                movement_type="receipt",
                quantity_delta=1,
                balance_after=before + 1,
                actor=foreign_user,
            )


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_mobile_detail_uses_live_data_and_prefixed_stock_forms(workspace):
    tenant, user, _, _, _, location = workspace
    with tenant_context(tenant):
        product = Product.objects.get(sku="Healthy")
    client = Client()
    client.force_login(user)
    detail_url = reverse("inventory:product_detail", args=[product.pk])
    response = client.get(detail_url, HTTP_HOST="acme.localhost")
    assert response.status_code == 200
    for value in (
        b'ui-detail-mobile',
        b'Stock &amp; Pricing',
        b'Inventory by Location',
        b'Recent Stock Movement',
        b'name="desktop-receive-location"',
        b'name="mobile-receive-location"',
    ):
        assert value in response.content
    response = client.post(
        reverse("inventory:product_stock_action", args=[product.pk, "receive"]),
        {
            "form_context": "mobile",
            "mobile-receive-location": location.pk,
            "mobile-receive-quantity": "2",
            "mobile-receive-note": "Mobile receipt",
        },
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 302
    with tenant_context(tenant):
        assert StockLevel.objects.get(product=product, location=location).quantity == 22
        assert StockMovement.objects.get(product=product).note == "Mobile receipt"
