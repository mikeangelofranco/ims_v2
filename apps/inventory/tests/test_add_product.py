from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from apps.dashboard.selectors import get_dashboard_snapshot
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Tenant, TenantDomain, TenantMembership, TenantRole

from ..models import (
    Category,
    Location,
    Product,
    ProductCustomField,
    ProductCustomValue,
    StockLevel,
    StockMovement,
)
from ..selectors import filtered_products
from ..services import change_stock
from ..validators import validate_product_image

pytestmark = pytest.mark.django_db


def payload(category_obj, **changes):
    return {
        "name": "New Product",
        "sku": "",
        "category": str(category_obj.pk),
        "selling_price": "1299.50",
        "unit_cost": "",
        "is_active": "active",
        "track_inventory": "on",
        "unit_of_measure": "pcs",
        "quantity": "8",
        "minimum_quantity": "20",
        "brand": "Core",
        "model": "V2",
        **changes,
    }


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_add_page_generated_sku_add_another_and_custom_values(workspace):
    tenant, user, *_ = workspace
    with tenant_context(tenant):
        category = Category.objects.get(slug="audio")
        field = ProductCustomField.objects.create(name="Warranty", key="warranty")
    client = Client()
    client.force_login(user)
    url = reverse("inventory:product_create")
    response = client.get(url, HTTP_HOST="acme.localhost")
    for heading in (
        b"Basic Information",
        b"Pricing",
        b"Inventory",
        b"Product Options",
        b"Additional Information",
    ):
        assert heading in response.content
    assert response.content.count(b"data-editor-panel-toggle") == 5
    assert b'data-default-expanded="true"' in response.content
    assert b'aria-controls="additional-fields"' in response.content
    assert b'name="save_action" value="add_another"' in response.content
    assert b"Foreign" not in response.content
    response = client.post(
        url,
        payload(
            category,
            custom_warranty="12 months",
            has_variants="on",
            description="D" * 500,
            save_action="add_another",
        ),
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 302
    assert response.url == url
    with tenant_context(tenant):
        product = Product.objects.get(name="New Product")
        assert product.sku.startswith("PRD-")
        assert product.brand == "Core" and product.model == "V2" and product.has_variants
        assert product.selling_price == Decimal("1299.50") and product.unit_cost == 0
        assert ProductCustomValue.objects.get(product=product, field=field).value == "12 months"
        assert StockLevel.objects.get(product=product).quantity == 8
        assert StockMovement.objects.get(product=product).actor == user
    fresh = client.get(url, HTTP_HOST="acme.localhost")
    assert not fresh.context["form"].is_bound


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_add_validation_and_untracked_products(workspace):
    tenant, user, *_ = workspace
    with tenant_context(tenant):
        category = Category.objects.get(slug="audio")
    client = Client()
    client.force_login(user)
    url = reverse("inventory:product_create")
    for changes, error_key in (
        ({"category": ""}, "category"),
        ({"selling_price": "-1"}, "selling_price"),
        ({"description": "D" * 501}, "description"),
    ):
        response = client.post(url, payload(category, **changes), HTTP_HOST="acme.localhost")
        assert response.status_code == 200 and error_key in response.context["form"].errors
    response = client.post(
        url,
        payload(
            category, track_inventory="", quantity="0", minimum_quantity="0", is_active="inactive"
        ),
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 302
    with tenant_context(tenant):
        product = Product.objects.get(name="New Product")
        assert not product.track_inventory and not product.is_active
        assert not StockLevel.objects.filter(product=product).exists()
        product.is_active = True
        product.save()
        assert filtered_products({"q": product.sku}).get().stock_status == "untracked"
        snapshot = get_dashboard_snapshot()
        assert snapshot.out_of_stock_count == 1
        assert snapshot.tracked_product_count == 3
        with pytest.raises(ValidationError, match="disabled"):
            change_stock(
                product=product,
                location=Location.objects.first(),
                quantity_delta=1,
                movement_type="receipt",
                actor=user,
            )
    response = client.post(url, payload(category, track_inventory=""), HTTP_HOST="acme.localhost")
    assert response.status_code == 200 and response.context["stock_form"].non_field_errors()


@override_settings(ALLOWED_HOSTS=["fresh.localhost"])
def test_first_product_provisions_default_location(client):
    tenant = Tenant.objects.create(name="Fresh", slug="fresh")
    TenantDomain.objects.create(tenant=tenant, hostname="fresh.localhost")
    user = get_user_model().objects.create_user(email="fresh@example.com", password="pass")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    with tenant_context(tenant):
        category = Category.objects.create(name="General", slug="general")
    client.force_login(user)
    response = client.post(
        reverse("inventory:product_create"), payload(category), HTTP_HOST="fresh.localhost"
    )
    assert response.status_code == 302
    with tenant_context(tenant):
        location = Location.objects.get(is_default=True)
        assert location.name == "Main Warehouse"
        assert StockLevel.objects.get(location=location).minimum_quantity == 20
        assert StockMovement.objects.get(location=location).balance_after == 8


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_inline_catalog_dialogs_and_custom_field_management(workspace):
    tenant, user, membership, foreign, *_ = workspace
    client = Client()
    client.force_login(user)
    category_url = reverse("inventory:category_create")
    response = client.post(
        category_url, {"name": "New Category"}, HTTP_HOST="acme.localhost", HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 200 and response["HX-Trigger"] == "catalogCreated"
    assert b'hx-swap-oob="outerHTML"' in response.content and b"New Category" in response.content
    response = client.post(
        category_url, {"name": "New Category"}, HTTP_HOST="acme.localhost", HTTP_HX_REQUEST="true"
    )
    assert response.context["form"].errors["name"]
    field_url = reverse("inventory:custom_field_create")
    response = client.post(
        field_url, {"name": "Warranty"}, HTTP_HOST="acme.localhost", HTTP_HX_REQUEST="true"
    )
    assert b"custom_warranty" in response.content and response["HX-Trigger"] == "catalogCreated"
    with tenant_context(tenant):
        definition = ProductCustomField.objects.get(key="warranty")
        product = Product.objects.first()
        value = ProductCustomValue.objects.create(
            product=product, field=definition, value="Lifetime"
        )
    with tenant_context(foreign.tenant):
        foreign_field = ProductCustomField.objects.create(name="Secret", key="secret")
        with pytest.raises(ValidationError, match="same workspace"):
            ProductCustomValue.objects.create(product=foreign, field=definition, value="Bad")
    manage_url = reverse("inventory:custom_fields")
    response = client.post(
        manage_url, {"field": definition.pk, "active": "false"}, HTTP_HOST="acme.localhost"
    )
    assert response.status_code == 302
    with tenant_context(tenant):
        assert ProductCustomValue.objects.get(pk=value.pk).value == "Lifetime"
    assert (
        client.post(manage_url, {"field": foreign_field.pk}, HTTP_HOST="acme.localhost").status_code
        == 404
    )
    assert client.post(manage_url, {"field": "bad"}, HTTP_HOST="acme.localhost").status_code == 404
    membership.role = TenantRole.MEMBER
    membership.save()
    assert client.get(field_url, HTTP_HOST="acme.localhost").status_code == 403
    assert client.get(category_url, HTTP_HOST="acme.localhost").status_code == 200


def test_image_limit_matches_five_megabyte_ui():
    validate_product_image(
        SimpleUploadedFile("valid.png", b"\x89PNG\r\n\x1a\n" + b"x" * (3 * 1024 * 1024))
    )
    with pytest.raises(ValidationError, match="5 MB"):
        validate_product_image(
            SimpleUploadedFile("large.png", b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024))
        )


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_mobile_inventory_panel_marks_server_errors_for_expansion(workspace):
    tenant, user, *_ = workspace
    with tenant_context(tenant):
        category = Category.objects.get(slug="audio")
    client = Client()
    client.force_login(user)
    response = client.post(
        reverse("inventory:product_create"),
        payload(category, quantity="-1"),
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 200
    assert "quantity" in response.context["stock_form"].errors
    assert b'data-default-expanded="false" data-has-errors="true"' in response.content


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_create_rejects_foreign_relationships_and_viewers(workspace):
    tenant, user, membership, foreign, foreign_category, location = workspace
    with tenant_context(tenant):
        category = Category.objects.get(slug="audio")
        before = Product.objects.count()
    with tenant_context(foreign.tenant):
        foreign_location = Location.objects.create(name="Foreign warehouse", code="foreign")
    client = Client()
    client.force_login(user)
    url = reverse("inventory:product_create")
    response = client.post(
        url, payload(category, category=str(foreign_category.pk)), HTTP_HOST="acme.localhost"
    )
    assert "category" in response.context["form"].errors
    response = client.post(
        url, payload(category, location=str(foreign_location.pk)), HTTP_HOST="acme.localhost"
    )
    assert "location" in response.context["stock_form"].errors
    with tenant_context(tenant):
        assert Product.objects.count() == before
        Location.objects.filter(pk=location.pk).update(is_default=False)
        Location.objects.create(name="Second", code="second")
    response = client.post(url, payload(category), HTTP_HOST="acme.localhost")
    assert "location" in response.context["stock_form"].errors
    response = client.post(
        url, payload(category, location=str(location.pk)), HTTP_HOST="acme.localhost"
    )
    assert response.status_code == 302
    membership.role = TenantRole.VIEWER
    membership.save()
    assert client.get(url, HTTP_HOST="acme.localhost").status_code == 403
    assert client.post(url, payload(category), HTTP_HOST="acme.localhost").status_code == 403
