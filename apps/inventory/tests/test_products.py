import io
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from apps.tenancy.context import tenant_context
from apps.tenancy.models import TenantDomain, TenantMembership, TenantRole

from ..csv_io import import_products, safe_csv_cell
from ..models import Category, Location, Product, StockLevel, StockMovement
from ..selectors import filtered_products, product_counts

pytestmark = pytest.mark.django_db


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_list_render_filters_and_htmx(workspace):
    tenant, user, *_ = workspace
    client = Client()
    client.force_login(user)
    url = reverse("inventory:product_list")
    response = client.get(url, HTTP_HOST="acme.localhost")
    assert response.status_code == 200
    assert b"Foreign secret" not in response.content
    assert b"Manage your product list" in response.content
    assert b"All Products" in response.content
    response = client.get(
        url, {"status": "low"}, HTTP_HOST="acme.localhost", HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 200
    assert b"<!doctype" not in response.content
    assert [p.name for p in response.context["page_obj"]] == ["Low"]
    with tenant_context(tenant):
        assert product_counts() == {"all": 4, "in": 1, "low": 1, "out": 1, "inactive": 1}
        assert list(filtered_products({"q": "Healthy-BAR"}))[0].name == "Healthy"
        assert filtered_products({"category": "bad"}).count() == 0
        assert list(filtered_products({"sort": "-stock"}))[0].name == "Healthy"


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_add_edit_validation_and_opening_stock(workspace):
    tenant, user, _, foreign, category, location = workspace
    client = Client()
    client.force_login(user)
    url = reverse("inventory:product_create")
    assert client.get(url, HTTP_HOST="acme.localhost").status_code == 200
    with tenant_context(tenant):
        local_category = Category.objects.get(slug="audio")
    data = {
        "name": "Cable",
        "sku": "CBL",
        "selling_price": "199",
        "unit_cost": "100",
        "is_active": "active",
        "track_inventory": "on",
        "category": local_category.pk,
        "quantity": "12",
        "minimum_quantity": "20",
        "location": location.pk,
    }
    response = client.post(url, data, HTTP_HOST="acme.localhost")
    assert response.status_code == 302
    with tenant_context(tenant):
        product = Product.objects.get(sku="CBL")
        assert product.selling_price == Decimal("199")
        assert product.updated_by == user
        assert StockLevel.objects.get(product=product).quantity == 12
        assert StockMovement.objects.get(product=product).balance_after == 12
    response = client.post(url, data, HTTP_HOST="acme.localhost")
    assert response.status_code == 200
    assert response.context["form"].errors["sku"]
    response = client.post(
        url, {**data, "sku": "SECOND", "category": category.pk}, HTTP_HOST="acme.localhost"
    )
    assert response.context["form"].errors["category"]
    edit_url = reverse("inventory:product_edit", args=[product.pk])
    response = client.post(edit_url, {**data, "name": "Updated"}, HTTP_HOST="acme.localhost")
    assert response.status_code == 302
    with tenant_context(tenant):
        assert Product.objects.get(pk=product.pk).name == "Updated"
        assert StockMovement.objects.filter(product=product).count() == 1
    assert (
        client.get(
            reverse("inventory:product_edit", args=[foreign.pk]), HTTP_HOST="acme.localhost"
        ).status_code
        == 404
    )


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_viewer_and_inactive_membership_denied(workspace):
    _, user, membership, *_ = workspace
    client = Client()
    client.force_login(user)
    membership.role = TenantRole.VIEWER
    membership.save()
    assert (
        client.get(reverse("inventory:product_list"), HTTP_HOST="acme.localhost").status_code == 200
    )
    for name in ("product_create", "product_import"):
        assert (
            client.get(reverse("inventory:" + name), HTTP_HOST="acme.localhost").status_code == 403
        )
    membership.is_active = False
    membership.save()
    assert (
        client.get(reverse("inventory:product_list"), HTTP_HOST="acme.localhost").status_code == 403
    )


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_export_selection_and_import_rollback(workspace):
    tenant, user, _, foreign, *_ = workspace
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("inventory:product_export"), {"selected": foreign.pk}, HTTP_HOST="acme.localhost"
    )
    assert response.status_code == 200
    assert b"Foreign secret" not in response.content
    response = client.get(
        reverse("inventory:product_export"), {"status": "low"}, HTTP_HOST="acme.localhost"
    )
    assert b"Low-BAR" in response.content and b"Healthy-BAR" not in response.content
    with tenant_context(tenant):
        with pytest.raises(ValidationError):
            import_products(file=io.BytesIO(b"name,sku\nNew,NEW\nDuplicate,Low\n"), actor=user)
        assert not Product.objects.filter(sku="NEW").exists()
    file = SimpleUploadedFile(
        "products.csv", b"name,sku,selling_price\nNew,NEW,29.50\n", content_type="text/csv"
    )
    response = client.post(
        reverse("inventory:product_import"), {"file": file}, HTTP_HOST="acme.localhost"
    )
    assert response.status_code == 302
    with tenant_context(tenant):
        assert Product.objects.get(sku="NEW").selling_price == Decimal("29.50")
    assert safe_csv_cell(" =SUM(A1)").startswith("'")


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_pagination_bad_inputs_and_csrf(workspace):
    _, user, *_ = workspace
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    response = client.get(
        reverse("inventory:product_list"),
        {"page": "bad", "per_page": "bad", "sort": "bad"},
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 200
    assert response.context["page_obj"].number == 1
    assert (
        client.post(reverse("inventory:product_create"), {}, HTTP_HOST="acme.localhost").status_code
        == 403
    )


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_product_images_are_validated_and_tenant_scoped(workspace, tmp_path):
    tenant, user, _, foreign, *_ = workspace
    client = Client()
    client.force_login(user)
    with override_settings(MEDIA_ROOT=tmp_path):
        with tenant_context(tenant):
            product = Product.objects.get(sku="Healthy")
            with pytest.raises(ValidationError):
                product.image = SimpleUploadedFile("unsafe.svg", b"<svg/>")
                product.save()
            product.image = SimpleUploadedFile("thumb.png", b"\x89PNG\r\n\x1a\npreview")
            product.save()
        response = client.get(
            reverse("inventory:product_image", args=[product.pk]), HTTP_HOST="acme.localhost"
        )
        assert response.status_code == 200
        assert response["Cache-Control"] == "private, no-store"
        assert response["Content-Type"] == "image/png"
        response = client.get(
            reverse("inventory:product_image", args=[foreign.pk]), HTTP_HOST="acme.localhost"
        )
        assert response.status_code == 404


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_list_pagination_preserves_search_and_category(workspace):
    tenant, user, *_ = workspace
    with tenant_context(tenant):
        category = Category.objects.get(slug="audio")
        for number in range(12):
            Product.objects.create(
                name=f"Cable {number:02}", sku=f"PAGE-{number}", category=category
            )
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("inventory:product_list"),
        {"q": "Cable", "category": str(category.pk), "page": "2", "per_page": "10", "sort": "name"},
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 200
    assert response.context["page_obj"].paginator.count == 12
    assert len(response.context["page_obj"]) == 2
    assert b"q=Cable&amp;category=" in response.content


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_dashboard_product_entry_points_use_current_host(workspace):
    from html.parser import HTMLParser

    from apps.businesses.models import BusinessProfile

    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.links.append(dict(attrs))

    tenant, user, *_ = workspace
    with tenant_context(tenant):
        BusinessProfile.objects.create(legal_name="Acme", industry="retail", company_size="solo")
    client = Client()
    client.force_login(user)
    response = client.get(reverse("onboarding:workspace_home"), HTTP_HOST="acme.localhost")
    assert response.status_code == 200
    parser = Links()
    parser.feed(response.content.decode())
    menus = [
        link
        for link in parser.links
        if link.get("class") in ("dashboard-nav__item", "dashboard-mobile-nav__item")
        and link.get("href") == reverse("inventory:product_list")
    ]
    assert len(menus) == 2
    assert any(link.get("href") == reverse("inventory:product_create") for link in parser.links)
    assert any(
        link.get("href") == reverse("inventory:product_list") + "?status=low"
        for link in parser.links
    )
    with tenant_context(tenant):
        low = Product.objects.get(sku="Low")
    assert any(
        link.get("href") == reverse("inventory:product_detail", args=[low.pk])
        for link in parser.links
    )
    assert response.content.count(f'action="{reverse("inventory:product_list")}"'.encode()) == 1
    assert all(not link.get("aria-disabled") for link in menus)


@override_settings(ALLOWED_HOSTS=["acme.localhost", "other.localhost"])
def test_product_routes_follow_host_even_for_user_with_two_memberships(workspace):
    tenant, user, _, foreign, *_ = workspace
    other = foreign.tenant
    TenantDomain.objects.create(tenant=other, hostname="other.localhost")
    TenantMembership.objects.create(tenant=other, user=user, role=TenantRole.OWNER)
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("inventory:product_list"), {"tenant": tenant.pk}, HTTP_HOST="other.localhost"
    )
    assert response.status_code == 200
    assert [product.pk for product in response.context["page_obj"]] == [foreign.pk]
    assert response.context["tenant"] == other
    with tenant_context(tenant):
        local = Product.objects.get(sku="Healthy")
    response = client.get(
        reverse("inventory:product_edit", args=[local.pk]), HTTP_HOST="other.localhost"
    )
    assert response.status_code == 404


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_mobile_cards_and_load_more_are_tenant_scoped(workspace):
    tenant, user, *_ = workspace
    with tenant_context(tenant):
        for number in range(10):
            Product.objects.create(name=f"Batch {number:02}", sku=f"BATCH-{number}")
    client = Client()
    client.force_login(user)
    url = reverse("inventory:product_list")
    response = client.get(url, {"q": "Batch"}, HTTP_HOST="acme.localhost")
    assert response.status_code == 200
    assert response.content.count(b"data-mobile-product=") == 6
    assert b"Load more products" in response.content
    assert b"Showing 6 of 10 products" in response.content
    first_ids = {p.pk for p in response.context["mobile_page"]}
    response = client.get(
        url,
        {"q": "Batch", "mobile_page": "2", "append": "mobile"},
        HTTP_HOST="acme.localhost",
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert response.content.count(b"data-mobile-product=") == 4
    assert b"<table" not in response.content and b"<!doctype" not in response.content
    assert b"Foreign secret" not in response.content
    assert b"Load more products" not in response.content
    assert b"Showing 10 of 10 products" in response.content
    assert first_ids.isdisjoint({p.pk for p in response.context["mobile_page"]})


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_location_filter_uses_location_stock_and_rejects_foreign_locations(workspace):
    tenant, user, _, foreign, _, location = workspace
    with tenant_context(foreign.tenant):
        foreign_location = Location.objects.create(name="Other storage", code="other-storage")
        StockLevel.objects.create(product=foreign, location=foreign_location, quantity=99)
    with tenant_context(tenant):
        second = Location.objects.create(name="Second", code="second")
        healthy = Product.objects.get(sku="Healthy")
        StockLevel.objects.create(product=healthy, location=second, quantity=2, minimum_quantity=3)
        product = filtered_products({"location": str(second.pk)}).get()
        assert product.pk == healthy.pk
        assert product.total_quantity == 2 and product.total_minimum == 3
        assert product.stock_status == "low"
        assert filtered_products({"location": str(foreign_location.pk)}).count() == 0
        assert filtered_products({"location": "invalid"}).count() == 0
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("inventory:product_list"),
        {"location": second.pk, "sort": "-price"},
        HTTP_HOST="acme.localhost",
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert len(response.context["mobile_page"]) == 1
    assert foreign_location not in response.context["locations"]
    assert b"Other storage" not in response.content


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_mobile_viewer_menu_has_export_but_no_edit(workspace):
    _, user, membership, *_ = workspace
    membership.role = TenantRole.VIEWER
    membership.save()
    client = Client()
    client.force_login(user)
    response = client.get(
        reverse("inventory:product_list"),
        {"append": "mobile"},
        HTTP_HOST="acme.localhost",
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert b"Export product" in response.content
    assert b"Edit product details" not in response.content


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_active_mobile_products_navigation_points_to_product_list(workspace):
    from html.parser import HTMLParser

    class ActiveLinks(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "a" and "dashboard-mobile-nav__item is-active" == values.get("class"):
                self.links.append(values)

    _, user, *_ = workspace
    client = Client()
    client.force_login(user)
    response = client.get(reverse("inventory:product_list"), HTTP_HOST="acme.localhost")
    parser = ActiveLinks()
    parser.feed(response.content.decode())
    assert len(parser.links) == 1
    assert parser.links[0]["href"] == reverse("inventory:product_list")
    assert parser.links[0]["aria-current"] == "page"
