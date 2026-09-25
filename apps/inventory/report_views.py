import csv

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .csv_io import safe_csv_cell
from .models import Category, Location
from .report_selectors import inventory_report_products, inventory_report_summary
from .views import workspace_context

REPORTS = {
    "inventory": (
        "Inventory Summary",
        "View all products with their current stock levels, minimum stock, "
        "and status across locations.",
    ),
    "low": (
        "Low Stock Report",
        "Products that have reached their minimum stock level and need attention.",
    ),
    "out": ("Out of Stock Report", "Products that currently have zero tracked stock."),
    "valuation": (
        "Inventory Valuation",
        "Current inventory value based on stock quantity and selling price.",
    ),
    "location": (
        "Stock by Location",
        "See how inventory is physically distributed across your locations.",
    ),
    "aging": (
        "Inventory Aging / No Movement",
        "Review inventory items and identify products that need attention.",
    ),
}


def _report_params(request):
    report_key = request.GET.get("report", "inventory")
    if report_key not in REPORTS:
        report_key = "inventory"
    params = request.GET.copy()
    if report_key == "low":
        params["status"] = "low"
    elif report_key == "out":
        params["status"] = "out"
    elif report_key == "valuation" and "sort" not in params:
        params["sort"] = "-value"
    return report_key, params


def _decorate_locations(products):
    for product in products:
        levels = product.report_stock_levels
        if not levels:
            product.report_location = "—"
        elif len(levels) == 1:
            product.report_location = levels[0].location.name
        else:
            product.report_location = f"{len(levels)} locations"


@login_required
@require_GET
def report_list(request):
    per_page_value = request.GET.get("per_page", "10")
    per_page = int(per_page_value) if per_page_value in {"10", "25", "50", "100"} else 10
    report_key, report_params = _report_params(request)
    products = inventory_report_products(report_params)
    page = Paginator(products, per_page).get_page(request.GET.get("page"))
    _decorate_locations(page.object_list)
    context = workspace_context(request)
    context.update(
        {
            "summary": inventory_report_summary(),
            "report_key": report_key,
            "report_title": REPORTS[report_key][0],
            "report_description": REPORTS[report_key][1],
            "page_obj": page,
            "page_range": page.paginator.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "categories": Category.objects.filter(is_active=True),
            "locations": Location.objects.filter(is_active=True),
            "per_page": per_page,
            "as_of": timezone.localtime(),
            "selected_status": report_params.get("status", "all"),
            "sort_headers": [
                (key, label, "-" + key if report_params.get("sort") == key else key)
                for key, label in (
                    ("name", "Product"),
                    ("sku", "SKU"),
                    ("category", "Category"),
                    ("stock", "Current Stock"),
                    ("minimum", "Min. Stock"),
                    ("status", "Status"),
                    ("value", "Inventory Value"),
                )
            ],
        }
    )
    return render(request, "inventory/report_list.html", context)


@login_required
@require_GET
def report_export(request):
    workspace_context(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="inventory-summary.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Product",
            "SKU",
            "Category",
            "Location",
            "Current stock",
            "Minimum stock",
            "Status",
            "Inventory value",
        ]
    )
    _, report_params = _report_params(request)
    products = inventory_report_products(report_params)
    _decorate_locations(products)
    for product in products:
        writer.writerow(
            [
                safe_csv_cell(value)
                for value in (
                    product.name,
                    product.sku,
                    product.category.name if product.category else "Uncategorized",
                    product.report_location,
                    product.total_quantity,
                    product.total_minimum,
                    product.stock_status,
                    product.report_value,
                )
            ]
        )
    return response
