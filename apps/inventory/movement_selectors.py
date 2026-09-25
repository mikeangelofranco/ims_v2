from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from django.db.models import Count, Q, Sum
from django.db.models.functions import Abs, Coalesce
from django.utils import timezone

from apps.tenancy.context import get_current_tenant
from apps.tenancy.models import TenantMembership

from .models import MovementType, StockMovement


@dataclass(frozen=True)
class MovementPeriod:
    start: date
    end: date


def selected_period(params):
    today = timezone.localdate()
    start = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    end = next_month - timedelta(days=1)
    try:
        requested_start = date.fromisoformat(params.get("date_from", ""))
        requested_end = date.fromisoformat(params.get("date_to", ""))
        if requested_start <= requested_end:
            start, end = requested_start, requested_end
    except (TypeError, ValueError):
        pass
    return MovementPeriod(start, end)


def logical_movements(period):
    return (
        StockMovement.objects.select_related(
            "product", "product__category", "location", "counterparty_location", "actor"
        )
        .filter(created_at__date__range=(period.start, period.end))
        .filter(~Q(movement_type=MovementType.TRANSFER) | Q(quantity_delta__lt=0))
    )


def filtered_movements(params, period):
    movements = logical_movements(period)
    movement_type = params.get("type", "all")
    if movement_type in MovementType.values:
        movements = movements.filter(movement_type=movement_type)
    location = params.get("location")
    if location:
        try:
            location = UUID(location)
        except (TypeError, ValueError):
            return movements.none()
        movements = movements.filter(
            Q(location_id=location) | Q(counterparty_location_id=location)
        )
    actor = params.get("user")
    if actor:
        try:
            actor = UUID(actor)
        except (TypeError, ValueError):
            return movements.none()
        movements = movements.filter(actor_id=actor)
    query = params.get("q", "").strip()
    if query:
        movements = movements.filter(
            Q(product__name__icontains=query)
            | Q(product__sku__icontains=query)
            | Q(reference__icontains=query)
            | Q(note__icontains=query)
        )
    sort = params.get("sort", "-created")
    orderings = {
        "created": "created_at",
        "-created": "-created_at",
        "product": "product__name",
        "-product": "-product__name",
        "type": "movement_type",
        "-type": "-movement_type",
        "quantity": "quantity_delta",
        "-quantity": "-quantity_delta",
        "location": "location__name",
        "-location": "-location__name",
        "reference": "reference",
        "-reference": "-reference",
        "user": "actor__first_name",
        "-user": "-actor__first_name",
    }
    return movements.order_by(orderings.get(sort, "-created_at"), "-created_at")


def movement_summary(period):
    movements = logical_movements(period)
    summary = {}
    for key in MovementType.values:
        values = movements.filter(movement_type=key).aggregate(
            quantity=Coalesce(Sum(Abs("quantity_delta")), 0), transactions=Count("pk")
        )
        summary[key] = values
    summary["all"] = {
        "quantity": sum(item["quantity"] for item in summary.values()),
        "transactions": sum(item["transactions"] for item in summary.values()),
    }
    return summary


def movement_users():
    return TenantMembership.objects.filter(
        tenant=get_current_tenant(),
        is_active=True,
        user__inventory_movements__tenant=get_current_tenant(),
    ).select_related("user").distinct().order_by("user__first_name", "user__email")
