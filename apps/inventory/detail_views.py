from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .detail_forms import GalleryImageForm, StockActionForm
from .detail_selectors import product_detail_data, product_detail_record
from .detail_services import (
    add_gallery_image,
    apply_stock_action,
    duplicate_product,
    set_product_archived,
)
from .models import ProductImage
from .services import require_product_editor
from .views import workspace_context

STOCK_ACTIONS = (
    ("receive", "Receive Stock", "Record incoming stock", "download"),
    ("adjust", "Adjust Stock", "Correct stock quantity", "arrow-left-right"),
    ("transfer", "Transfer Stock", "Move stock between locations", "boxes"),
)


def stock_action_context(*, prefix, active_kind=None, active_form=None):
    return [
        {
            "kind": kind,
            "title": title,
            "copy": copy,
            "icon": icon,
            "form": active_form
            if kind == active_kind and active_form is not None
            else StockActionForm(kind=kind, prefix=f"{prefix}-{kind}"),
        }
        for kind, title, copy, icon in STOCK_ACTIONS
    ]


def detail_response(
    request,
    product,
    *,
    active_kind=None,
    active_form=None,
    active_context="desktop",
    gallery_form=None,
):
    context = workspace_context(request)
    context.update(
        product_detail_data(
            product,
            show_all_activity=request.GET.get("activity") == "all",
            activity_page=request.GET.get("page"),
        )
    )
    context.update(
        {
            "product": product,
            "stock_actions": stock_action_context(
                prefix="desktop",
                active_kind=active_kind if active_context == "desktop" else None,
                active_form=active_form if active_context == "desktop" else None,
            ),
            "mobile_stock_actions": stock_action_context(
                prefix="mobile",
                active_kind=active_kind if active_context == "mobile" else None,
                active_form=active_form if active_context == "mobile" else None,
            ),
            "active_kind": active_kind,
            "active_context": active_context,
            "gallery_form": gallery_form or GalleryImageForm(),
        }
    )
    return render(request, "inventory/product_detail.html", context)


def scoped_product(pk):
    product = product_detail_record(pk)
    if product is None:
        raise Http404("Product not found.")
    return product


@login_required
@require_GET
def product_detail(request, pk):
    workspace_context(request)
    return detail_response(request, scoped_product(pk))


@login_required
@require_POST
def product_stock_action(request, pk, kind):
    if kind not in {action[0] for action in STOCK_ACTIONS}:
        raise Http404("Stock action not found.")
    workspace_context(request)
    require_product_editor(request.user)
    product = scoped_product(pk)
    submitted_context = request.POST.get("form_context")
    form_context = submitted_context if submitted_context in {"desktop", "mobile"} else "desktop"
    form = StockActionForm(
        request.POST,
        kind=kind,
        prefix=f"{form_context}-{kind}" if submitted_context else None,
    )
    if form.is_valid():
        try:
            apply_stock_action(
                product=product, kind=kind, data=form.cleaned_data, actor=request.user
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Stock updated.")
            return redirect("inventory:product_detail", pk=pk)
    return detail_response(
        request,
        product,
        active_kind=kind,
        active_form=form,
        active_context=form_context,
    )


@login_required
@require_POST
def product_duplicate(request, pk):
    workspace_context(request)
    require_product_editor(request.user)
    try:
        duplicate = duplicate_product(source=scoped_product(pk), actor=request.user)
    except ValidationError, IntegrityError:
        messages.error(request, "Could not duplicate this product. Please try again.")
        return redirect("inventory:product_detail", pk=pk)
    messages.success(request, "Product duplicated as an inactive item with no opening stock.")
    return redirect("inventory:product_detail", pk=duplicate.pk)


@login_required
@require_POST
def product_archive(request, pk):
    workspace_context(request)
    require_product_editor(request.user)
    product = scoped_product(pk)
    set_product_archived(product=product, archived=product.is_active, actor=request.user)
    messages.success(
        request, "Product archived." if not product.is_active else "Product reactivated."
    )
    return redirect("inventory:product_detail", pk=pk)


@login_required
@require_POST
def product_gallery_upload(request, pk):
    workspace_context(request)
    require_product_editor(request.user)
    product = scoped_product(pk)
    form = GalleryImageForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            add_gallery_image(product=product, actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            if hasattr(exc, "message_dict"):
                for field, errors in exc.message_dict.items():
                    form.add_error(field if field in form.fields else None, errors)
            else:
                form.add_error(None, exc)
        else:
            messages.success(request, "Product image added.")
            return redirect("inventory:product_detail", pk=pk)
    return detail_response(request, product, gallery_form=form)


@login_required
@require_GET
def product_gallery_image(request, pk, image_pk):
    workspace_context(request)
    product = scoped_product(pk)
    photo = get_object_or_404(ProductImage.objects.filter(product=product), pk=image_pk)
    response = FileResponse(photo.image.open("rb"))
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_GET
def product_label(request, pk):
    context = workspace_context(request)
    product = scoped_product(pk)
    return render(request, "inventory/product_label.html", {**context, "product": product})
