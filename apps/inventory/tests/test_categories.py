import pytest
from django.core.exceptions import ValidationError
from django.test import Client, override_settings
from django.urls import reverse

from apps.tenancy.context import tenant_context
from apps.tenancy.models import TenantRole

from ..models import Category, Product
from ..product_forms import ProductCreateForm

pytestmark = pytest.mark.django_db


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_category_list_counts_filters_products_and_tenant_data(workspace):
    tenant, user, _, foreign, foreign_category, _ = workspace
    with tenant_context(tenant):
        audio = Category.objects.get(slug="audio")
        audio.description = "Earbuds and speakers"
        audio.code = "CAT-001"
        audio.updated_by = user
        audio.save()
        inactive = Category.objects.create(
            name="Legacy", slug="legacy", code="CAT-002", is_active=False
        )
        Product.objects.create(name="Unsorted", sku="UNSORTED")
    client = Client()
    client.force_login(user)
    response = client.get(reverse("inventory:category_list"), HTTP_HOST="acme.localhost")
    assert response.status_code == 200
    assert response.context["total_categories"] == 2
    assert response.context["active_categories"] == 1
    assert response.context["uncategorized_products"] == 1
    listed_audio = next(item for item in response.context["page_obj"] if item.pk == audio.pk)
    assert listed_audio.product_count == 4
    for value in (b"Audio", b"CAT-001", b"Earbuds and speakers", b"Legacy"):
        assert value in response.content
    assert foreign.name.encode() not in response.content
    assert foreign_category.name.encode() not in response.content
    response = client.get(
        reverse("inventory:category_list"),
        {"q": "legacy", "status": "inactive"},
        HTTP_HOST="acme.localhost",
    )
    assert list(response.context["page_obj"]) == [inactive]


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_category_create_edit_status_and_product_assignment(workspace):
    tenant, user, membership, foreign, foreign_category, _ = workspace
    client = Client()
    client.force_login(user)
    create_url = reverse("inventory:category_create")
    response = client.post(
        create_url,
        {
            "name": "Networking",
            "code": "net-01",
            "description": "Routers and network gear",
            "icon": "wifi",
            "is_active": "on",
        },
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 302
    with tenant_context(tenant):
        category = Category.objects.get(name="Networking")
        assert category.code == "NET-01"
        assert category.created_by == user and category.updated_by == user
        product = Product.objects.get(sku="Healthy")
        product.category = category
        product.save()
    response = client.post(
        reverse("inventory:category_edit", args=[category.pk]),
        {
            "name": "Network Equipment",
            "code": "NET-02",
            "description": "Switches and routers",
            "icon": "plug",
        },
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 302
    with tenant_context(tenant):
        category.refresh_from_db()
        assert category.name == "Network Equipment" and category.code == "NET-02"
        assert not category.is_active
        assert Product.objects.get(pk=product.pk).category == category
        assert category not in ProductCreateForm().fields["category"].queryset
    assert (
        client.get(
            reverse("inventory:category_edit", args=[foreign_category.pk]),
            HTTP_HOST="acme.localhost",
        ).status_code
        == 404
    )
    assert (
        client.post(
            reverse("inventory:category_status", args=[foreign_category.pk]),
            {"active": "true"},
            HTTP_HOST="acme.localhost",
        ).status_code
        == 404
    )
    response = client.post(
        reverse("inventory:category_status", args=[category.pk]),
        {"active": "true"},
        HTTP_HOST="acme.localhost",
    )
    assert response.status_code == 302
    with tenant_context(tenant):
        category.refresh_from_db()
        assert category.is_active
    membership.role = TenantRole.VIEWER
    membership.save()
    assert (
        client.get(reverse("inventory:category_list"), HTTP_HOST="acme.localhost").status_code
        == 200
    )
    assert client.get(create_url, HTTP_HOST="acme.localhost").status_code == 403
    assert (
        client.post(
            reverse("inventory:category_status", args=[category.pk]),
            {"active": "false"},
            HTTP_HOST="acme.localhost",
        ).status_code
        == 403
    )


def test_category_codes_are_unique_per_tenant_and_auto_generated(workspace):
    tenant, user, _, foreign, _, _ = workspace
    with tenant_context(tenant):
        category = Category.objects.create(name="Auto", slug="auto")
        assert category.code.startswith("CAT-")
        with pytest.raises(ValidationError):
            Category.objects.create(name="Duplicate", slug="duplicate", code=category.code)
    with tenant_context(foreign.tenant):
        with pytest.raises(ValidationError, match="same workspace"):
            Category.objects.create(
                name="Invalid actor", slug="invalid-actor", created_by=user
            )


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_mobile_category_feed_filters_and_loads_more(workspace):
    tenant, user, _, _, _, _ = workspace
    with tenant_context(tenant):
        for number in range(7):
            Category.objects.create(
                name=f"Mobile {number}",
                slug=f"mobile-{number}",
                code=f"MOB-{number}",
                is_active=number != 6,
            )
        Product.objects.create(name="Needs category", sku="NEEDS-CATEGORY")
    client = Client()
    client.force_login(user)
    url = reverse("inventory:category_list")
    response = client.get(url, {"q": "Mobile"}, HTTP_HOST="acme.localhost")
    assert response.status_code == 200
    assert len(response.context["mobile_page"]) == 6
    assert b"ui-category-mobile-panel" in response.content
    assert b"Load more categories" in response.content
    first_ids = {category.pk for category in response.context["mobile_page"]}
    response = client.get(
        url,
        {"q": "Mobile", "mobile_page": "2", "append": "categories"},
        HTTP_HOST="acme.localhost",
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert first_ids.isdisjoint({category.pk for category in response.context["mobile_page"]})
    assert b"ui-category-card" in response.content and b"<!doctype" not in response.content
    response = client.get(
        url,
        {"q": "Mobile", "status": "inactive", "mobile": "1"},
        HTTP_HOST="acme.localhost",
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert [category.name for category in response.context["mobile_page"]] == ["Mobile 6"]
    assert b'id="mobile-category-panel"' in response.content
    products = client.get(
        reverse("inventory:product_list"),
        {"category": "uncategorized"},
        HTTP_HOST="acme.localhost",
    )
    assert [product.sku for product in products.context["page_obj"]] == ["NEEDS-CATEGORY"]
