import csv

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.businesses.models import BusinessProfile
from apps.tenancy.models import TenantMembership, TenantRole

from .csv_io import IMPORT_FIELDS, import_products, safe_csv_cell
from .forms import OpeningStockForm, ProductForm, ProductImportForm
from .models import Category, Location, Product
from .product_forms import ProductCreateForm
from .selectors import SORTS, STATUSES, filtered_products, product_counts
from .services import require_product_editor, save_product


def workspace_context(request):
    membership = get_object_or_404(
        TenantMembership,
        tenant=request.tenant,
        user=request.user,
        is_active=True,
    )
    business = BusinessProfile.objects.first()
    route_name = request.resolver_match.url_name if request.resolver_match else ""
    products_active = route_name.startswith("product")
    categories_active = route_name.startswith("category")
    return {
        "tenant": request.tenant,
        "membership": membership,
        "business": business,
        "can_edit": membership.role != TenantRole.VIEWER,
        "can_manage_fields": membership.role in (TenantRole.OWNER, TenantRole.ADMIN),
        "products_active": products_active,
        "categories_active": categories_active,
        "catalog_nav_active": products_active or categories_active,
        "stock_active": route_name.startswith("movement"),
        "reports_active": route_name.startswith("report"),
        "workspace_display_url": f"{request.tenant.slug}.{settings.WORKSPACE_DISPLAY_DOMAIN}",
        "currency_symbol": "₱"
        if not business or business.currency == "PHP"
        else business.currency + " ",
    }


@login_required
@require_GET
def product_list(request):
    context = workspace_context(request)
    per_page = request.GET.get("per_page", "10")
    per_page = int(per_page) if per_page in ("10", "25", "50", "100") else 10
    products = filtered_products(request.GET)
    page = Paginator(products, per_page).get_page(request.GET.get("page"))
    mobile_page = Paginator(products, 6).get_page(request.GET.get("mobile_page"))
    counts = product_counts()
    sort = request.GET.get("sort", "name")
    context.update(
        {
            "page_obj": page,
            "mobile_page": mobile_page,
            "locations": Location.objects.filter(is_active=True),
            "selected_sort": sort
            if sort.lstrip("-") in SORTS
            else ("-name" if sort.startswith("-") else "name"),
            "sort_options": (
                ("name", "Name (A–Z)"),
                ("-name", "Name (Z–A)"),
                ("sku", "SKU (A–Z)"),
                ("-sku", "SKU (Z–A)"),
                ("category", "Category (A–Z)"),
                ("-category", "Category (Z–A)"),
                ("price", "Price (low to high)"),
                ("-price", "Price (high to low)"),
                ("stock", "Stock (low to high)"),
                ("-stock", "Stock (high to low)"),
                ("minimum", "Minimum (low to high)"),
                ("-minimum", "Minimum (high to low)"),
                ("status", "Status (A–Z)"),
                ("-status", "Status (Z–A)"),
                ("updated", "Oldest update"),
                ("-updated", "Recently updated"),
            ),
            "counts": counts,
            "per_page": per_page,
            "categories": Category.objects.all(),
            "status": request.GET.get("status", "all"),
            "tabs": [(key, label, counts[key]) for key, label in STATUSES],
            "sort_headers": [
                (key, label, ("-" + key if sort == key else key))
                for key, label in (
                    ("name", "Product"),
                    ("sku", "SKU"),
                    ("category", "Category"),
                    ("stock", "Current Stock"),
                    ("minimum", "Min. Stock"),
                    ("price", "Price"),
                    ("status", "Status"),
                    ("updated", "Updated"),
                )
                if key in SORTS
            ],
            "page_range": page.paginator.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
        }
    )
    template = (
        "inventory/partials/list_panel.html"
        if request.headers.get("HX-Request") == "true"
        else "inventory/product_list.html"
    )
    if request.headers.get("HX-Request") == "true" and request.GET.get("append") == "mobile":
        template = "inventory/partials/mobile_batch.html"
        context["appending"] = True
    response = render(request, template, context)
    response.headers["Vary"] = "HX-Request"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def product_create(request):
    context = workspace_context(request)
    require_product_editor(request.user)
    form = ProductCreateForm(
        request.POST if request.method == "POST" else None, request.FILES or None
    )
    valid = form.is_valid() if request.method == "POST" else False
    stock_form = OpeningStockForm(
        request.POST if request.method == "POST" else None,
        compact=True,
        tracking=form.cleaned_data.get("track_inventory", True) if valid else True,
    )
    if request.method == "POST":
        stock_valid = stock_form.is_valid()
        if valid and stock_valid:
            try:
                save_product(form=form, actor=request.user, opening_stock=stock_form.cleaned_data)
            except ValidationError, IntegrityError:
                form.add_error(
                    None, "Unable to save. Check for duplicate SKU or barcode and retry."
                )
            else:
                messages.success(request, "Product added.")
                return redirect(
                    "inventory:product_create"
                    if request.POST.get("save_action") == "add_another"
                    else "inventory:product_list"
                )
    return render(
        request,
        "inventory/product_create.html",
        {**context, "form": form, "stock_form": stock_form, "heading": "Add Product"},
    )


@login_required
@require_http_methods(["GET", "POST"])
def product_edit(request, pk):
    context = workspace_context(request)
    require_product_editor(request.user)
    product = get_object_or_404(Product.objects.all(), pk=pk)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        try:
            save_product(form=form, actor=request.user)
        except ValidationError, IntegrityError:
            form.add_error(None, "Unable to save. Check for duplicate SKU or barcode and retry.")
        else:
            messages.success(request, "Product updated.")
            return redirect("inventory:product_detail", pk=product.pk)
    return render(
        request, "inventory/product_form.html", {**context, "form": form, "heading": "Edit Product"}
    )


@login_required
@require_GET
def product_export(request):
    workspace_context(request)
    products = filtered_products(request.GET)
    selected = request.GET.getlist("selected")
    if selected:
        from uuid import UUID

        try:
            products = products.filter(pk__in=[UUID(value) for value in selected[:100]])
        except ValueError:
            return HttpResponse("Invalid product selection.", status=400)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="products.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow((*IMPORT_FIELDS, "category", "current_stock", "minimum_stock", "status"))
    for product in products.iterator(chunk_size=500):
        writer.writerow(
            [safe_csv_cell(getattr(product, field)) for field in IMPORT_FIELDS]
            + [
                safe_csv_cell(product.category),
                product.total_quantity,
                product.total_minimum,
                product.stock_status,
            ]
        )
    return response


@login_required
@require_http_methods(["GET", "POST"])
def product_import(request):
    context = workspace_context(request)
    require_product_editor(request.user)
    form = ProductImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            count = import_products(file=form.cleaned_data["file"], actor=request.user)
        except ValidationError as exc:
            form.add_error("file", exc)
        except IntegrityError:
            form.add_error(
                "file", "An imported SKU or barcode already exists. No products were imported."
            )
        else:
            messages.success(request, f"Imported {count} products.")
            return redirect("inventory:product_list")
    return render(request, "inventory/product_import.html", {**context, "form": form})


@login_required
@require_GET
def product_image(request, pk):
    workspace_context(request)
    product = get_object_or_404(Product.objects.exclude(image=""), pk=pk)
    response = FileResponse(product.image.open("rb"))
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
