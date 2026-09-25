from decimal import Decimal

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from apps.tenancy.context import tenant_context

from ..models import Location, Product, StockLevel
from ..report_selectors import inventory_report_products, inventory_report_summary

pytestmark = pytest.mark.django_db


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_inventory_report_totals_rows_and_filters_are_tenant_scoped(workspace):
    tenant, user, _, foreign, _, main = workspace
    with tenant_context(tenant):
        healthy = Product.objects.get(sku="Healthy")
        healthy.selling_price = Decimal("100")
        healthy.save()
        low = Product.objects.get(sku="Low")
        low.selling_price = Decimal("10")
        low.save()
        branch = Location.objects.create(name="Branch", code="branch")
        StockLevel.objects.create(
            product=healthy, location=branch, quantity=3, minimum_quantity=1
        )
        summary = inventory_report_summary()
        assert summary.total_products == 4
        assert summary.total_stock == 38
        assert summary.inventory_value == Decimal("2350")
        assert summary.low_stock == 1
        assert summary.out_of_stock == 1
        assert summary.stock_alerts == 2
        assert inventory_report_products({"q": foreign.name}).count() == 0

    client = Client()
    client.force_login(user)
    url = reverse("inventory:report_list")
    response = client.get(url, HTTP_HOST="acme.localhost")
    assert response.status_code == 200
    assert b"Inventory Summary" in response.content
    assert b"Foreign secret" not in response.content
    row = next(item for item in response.context["page_obj"] if item.pk == healthy.pk)
    assert row.total_quantity == 23
    assert row.report_value == Decimal("2300")
    assert row.report_location == "2 locations"

    filtered = client.get(
        url,
        {"location": main.pk, "q": "Healthy"},
        HTTP_HOST="acme.localhost",
    )
    item = filtered.context["page_obj"].object_list[0]
    assert item.total_quantity == 20
    assert item.report_value == Decimal("2000")
    assert item.report_location == "Main"
    invalid = client.get(url, {"location": "bad"}, HTTP_HOST="acme.localhost")
    assert invalid.context["page_obj"].paginator.count == 0


@override_settings(ALLOWED_HOSTS=["acme.localhost"])
def test_report_variants_and_export_follow_current_workspace(workspace):
    tenant, user, _, _, _, _ = workspace
    client = Client()
    client.force_login(user)
    url = reverse("inventory:report_list")
    response = client.get(url, {"report": "low"}, HTTP_HOST="acme.localhost")
    assert response.status_code == 200
    assert response.context["report_key"] == "low"
    assert [product.name for product in response.context["page_obj"]] == ["Low"]
    response = client.get(url, {"report": "out"}, HTTP_HOST="acme.localhost")
    assert [product.name for product in response.context["page_obj"]] == ["Empty"]

    export = client.get(
        reverse("inventory:report_export"),
        {"q": "Healthy"},
        HTTP_HOST="acme.localhost",
    )
    assert export.status_code == 200
    assert export["Content-Type"] == "text/csv"
    assert b"Healthy" in export.content
    assert b"Foreign secret" not in export.content
    with tenant_context(tenant):
        assert Product.objects.count() == 4
