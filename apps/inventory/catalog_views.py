from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .catalog_forms import CategoryCreateForm, CategoryForm, CustomFieldCreateForm
from .category_selectors import CATEGORY_SORTS, category_summary, filtered_categories
from .models import Category, ProductCustomField
from .product_forms import ProductCreateForm
from .product_services import (
    create_category,
    create_custom_field,
    require_custom_field_admin,
    set_category_active,
    set_custom_field_active,
    update_category,
)
from .services import require_product_editor
from .views import workspace_context


@login_required
@require_GET
def category_list(request):
    context = workspace_context(request)
    per_page = request.GET.get("per_page", "10")
    per_page = int(per_page) if per_page in ("10", "25", "50", "100") else 10
    categories = filtered_categories(request.GET)
    page = Paginator(categories, per_page).get_page(request.GET.get("page"))
    mobile_page = Paginator(categories, 6).get_page(request.GET.get("mobile_page"))
    sort = request.GET.get("sort", "name")
    context.update(
        {
            **category_summary(),
            "page_obj": page,
            "mobile_page": mobile_page,
            "page_range": page.paginator.get_elided_page_range(
                page.number, on_each_side=2, on_ends=1
            ),
            "per_page": per_page,
            "selected_status": request.GET.get("status", "all"),
            "selected_sort": sort if sort.lstrip("-") in CATEGORY_SORTS else "name",
            "category_sort_options": (
                ("name", "Name (A–Z)"),
                ("-name", "Name (Z–A)"),
                ("products", "Products (low to high)"),
                ("-products", "Products (high to low)"),
                ("updated", "Oldest updated"),
                ("-updated", "Recently updated"),
            ),
            "sort_headers": [
                (key, label, ("-" + key if sort == key else key))
                for key, label in (
                    ("name", "Category"),
                    ("description", "Description"),
                    ("products", "Products"),
                    ("status", "Status"),
                    ("updated", "Updated"),
                )
            ],
        }
    )
    if request.headers.get("HX-Request") == "true":
        if request.GET.get("append") == "categories":
            context["appending"] = True
            return render(request, "inventory/partials/category_mobile_batch.html", context)
        if request.GET.get("mobile") == "1":
            return render(request, "inventory/partials/category_mobile_panel.html", context)
    return render(request, "inventory/category_list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def category_create(request):
    context = workspace_context(request)
    require_product_editor(request.user)
    is_htmx = request.headers.get("HX-Request") == "true"
    form_class = CategoryCreateForm if is_htmx else CategoryForm
    form = form_class(request.POST if request.method == "POST" else None, auto_id="category_%s")
    if request.method == "POST" and form.is_valid():
        try:
            category = create_category(
                name=form.cleaned_data["name"],
                actor=request.user,
                code=form.cleaned_data.get("code", ""),
                description=form.cleaned_data.get("description", ""),
                icon=form.cleaned_data.get("icon", "folder"),
                is_active=form.cleaned_data.get("is_active", True),
            )
        except ValidationError, IntegrityError:
            form.add_error(
                "name", "Unable to create category. Check for an existing category name."
            )
        else:
            if is_htmx:
                response = render(
                    request,
                    "inventory/partials/category_created.html",
                    {
                        "product_form": ProductCreateForm(initial={"category": category.pk}),
                    },
                )
                response["HX-Trigger"] = "catalogCreated"
                return response
            messages.success(request, "Category created.")
            return redirect("inventory:category_list")
    template = (
        "inventory/partials/catalog_dialog.html"
        if is_htmx
        else "inventory/category_form.html"
    )
    return render(
        request,
        template,
        {
            **context,
            "form": form,
            "heading": "Create Category",
            "action_url": "inventory:category_create",
            "submit_label": "Save Category",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def category_edit(request, pk):
    context = workspace_context(request)
    require_product_editor(request.user)
    category = get_object_or_404(Category.objects.all(), pk=pk)
    form = CategoryForm(request.POST or None, instance=category, auto_id="category_%s")
    if request.method == "POST" and form.is_valid():
        try:
            update_category(category=category, data=form.cleaned_data, actor=request.user)
        except (ValidationError, IntegrityError):
            form.add_error(None, "Unable to update this category. Check its name and code.")
        else:
            messages.success(request, "Category updated.")
            return redirect("inventory:category_list")
    return render(
        request,
        "inventory/category_form.html",
        {
            **context,
            "form": form,
            "category": category,
            "heading": "Edit Category",
            "action_url": "inventory:category_edit",
            "submit_label": "Save Changes",
        },
    )


@login_required
@require_POST
def category_status(request, pk):
    workspace_context(request)
    require_product_editor(request.user)
    category = get_object_or_404(Category.objects.all(), pk=pk)
    set_category_active(
        category=category,
        is_active=request.POST.get("active") == "true",
        actor=request.user,
    )
    messages.success(
        request, "Category activated." if category.is_active else "Category deactivated."
    )
    return redirect("inventory:category_list")


@login_required
@require_http_methods(["GET", "POST"])
def custom_field_create(request):
    context = workspace_context(request)
    require_custom_field_admin(request.user)
    form = CustomFieldCreateForm(
        request.POST if request.method == "POST" else None, auto_id="custom_field_%s"
    )
    if request.method == "POST" and form.is_valid():
        try:
            definition = create_custom_field(name=form.cleaned_data["name"], actor=request.user)
        except ValidationError, IntegrityError:
            form.add_error("name", "Unable to create field. Check for an existing field name.")
        else:
            if request.headers.get("HX-Request") == "true":
                product_form = ProductCreateForm()
                response = render(
                    request,
                    "inventory/partials/custom_field_created.html",
                    {
                        "field": product_form[f"custom_{definition.key}"],
                    },
                )
                response["HX-Trigger"] = "catalogCreated"
                return response
            messages.success(request, "Custom field created.")
            return redirect("inventory:custom_fields")
    template = (
        "inventory/partials/catalog_dialog.html"
        if request.headers.get("HX-Request") == "true"
        else "inventory/catalog_create.html"
    )
    return render(
        request,
        template,
        {
            **context,
            "form": form,
            "heading": "Create Custom Field",
            "action_url": "inventory:custom_field_create",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def custom_fields(request):
    context = workspace_context(request)
    require_custom_field_admin(request.user)
    if request.method == "POST":
        from uuid import UUID

        try:
            field_id = UUID(request.POST.get("field", ""))
        except (ValueError, TypeError, AttributeError) as exc:
            raise Http404("Custom field not found.") from exc
        definition = get_object_or_404(ProductCustomField.objects.all(), pk=field_id)
        set_custom_field_active(
            definition=definition,
            is_active=request.POST.get("active") == "true",
            actor=request.user,
        )
        messages.success(request, "Custom field updated. Existing product values are retained.")
        return redirect("inventory:custom_fields")
    return render(
        request,
        "inventory/custom_fields.html",
        {**context, "definitions": ProductCustomField.objects.all()},
    )
