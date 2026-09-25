import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from .csv_io import safe_csv_cell
from .detail_services import apply_stock_action
from .models import Location, MovementType
from .movement_forms import MovementActionForm
from .movement_selectors import (
    filtered_movements,
    movement_summary,
    movement_users,
    selected_period,
)
from .services import require_product_editor
from .views import workspace_context


def _movement_context(request):
    period = selected_period(request.GET)
    per_page_value = request.GET.get("per_page", "10")
    per_page = int(per_page_value) if per_page_value in {"10", "25", "50", "100"} else 10
    movements = filtered_movements(request.GET, period)
    page = Paginator(movements, per_page).get_page(request.GET.get("page"))
    summary = movement_summary(period)
    active_filter_count = sum(
        bool(request.GET.get(name)) for name in ("location", "user")
    )
    kind = request.GET.get("action") if request.GET.get("action") in {
        "receive", "adjust", "transfer"
    } else None
    return {
        **workspace_context(request),
        "period": period,
        "page_obj": page,
        "page_range": page.paginator.get_elided_page_range(
            page.number, on_each_side=2, on_ends=1
        ),
        "summary": summary,
        "locations": Location.objects.filter(is_active=True),
        "movement_users": movement_users(),
        "movement_types": MovementType.choices,
        "selected_type": request.GET.get("type", "all"),
        "per_page": per_page,
        "active_filter_count": active_filter_count,
        "action_kind": kind,
        "action_form": MovementActionForm(kind=kind) if kind else None,
    }


@login_required
@require_http_methods(["GET", "POST"])
def movement_list(request):
    if request.method == "POST":
        require_product_editor(request.user)
        kind = request.POST.get("action")
        if kind not in {"receive", "adjust", "transfer"}:
            return HttpResponse("Unknown stock action.", status=400)
        form = MovementActionForm(request.POST, kind=kind)
        if form.is_valid():
            try:
                apply_stock_action(
                    product=form.cleaned_data["product"],
                    kind=kind,
                    data=form.cleaned_data,
                    actor=request.user,
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, "Stock movement recorded.")
                return redirect("inventory:movement_list")
        context = _movement_context(request)
        context.update({"action_kind": kind, "action_form": form})
        return render(request, "inventory/movement_list.html", context, status=400)
    return render(request, "inventory/movement_list.html", _movement_context(request))


@login_required
@require_GET
def movement_export(request):
    workspace_context(request)
    period = selected_period(request.GET)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="stock-movements.csv"'
    writer = csv.writer(response)
    writer.writerow(
        ["Date and time", "Product", "SKU", "Type", "Quantity", "Location / route",
         "Reference", "User", "Remarks"]
    )
    for movement in filtered_movements(request.GET, period):
        route = movement.location.name
        if movement.counterparty_location_id:
            route = f"{route} -> {movement.counterparty_location.name}"
        writer.writerow(
            [
                safe_csv_cell(value)
                for value in (
                    movement.created_at.isoformat(),
                    movement.product.name,
                    movement.product.sku,
                    movement.get_movement_type_display(),
                    movement.quantity_delta,
                    route,
                    movement.reference,
                    movement.actor.get_full_name() if movement.actor else "System",
                    movement.note,
                )
            ]
        )
    return response
