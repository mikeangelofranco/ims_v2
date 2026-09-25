from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import ProductCustomValue, ProductEvent, ProductImage, StockLevel, StockMovement
from .selectors import product_inventory


def product_detail_record(pk):
    return product_inventory().select_related("created_by").filter(pk=pk).first()


def product_detail_data(product, *, show_all_activity=False, activity_page=None):
    levels = list(
        StockLevel.objects.filter(product=product)
        .select_related("location")
        .order_by("location__name")
    )
    total = sum(level.quantity for level in levels)
    locations = [
        {
            "name": level.location.name,
            "quantity": level.quantity,
            "share": (100 * level.quantity / total) if total else 0,
        }
        for level in levels
    ]
    movements = list(
        StockMovement.objects.filter(product=product)
        .select_related("actor", "location")
        .order_by("-created_at", "-pk")[:5]
    )
    cutoff = timezone.now() - timedelta(days=30)
    sums = StockMovement.objects.filter(product=product, created_at__gte=cutoff).aggregate(
        received=Coalesce(Sum("quantity_delta", filter=Q(movement_type="receipt")), Value(0)),
        issued=Coalesce(Sum("quantity_delta", filter=Q(movement_type="issue")), Value(0)),
        adjusted=Coalesce(Sum("quantity_delta", filter=Q(movement_type="adjustment")), Value(0)),
    )
    activity = ProductEvent.objects.filter(product=product).select_related("actor")
    activity_page_obj = (
        Paginator(activity, 20).get_page(activity_page) if show_all_activity else None
    )
    events = activity_page_obj if activity_page_obj else activity[:5]
    return {
        "locations": locations,
        "total_stock": total,
        "minimum_stock": sum(level.minimum_quantity for level in levels),
        "movements": movements,
        "received_30d": sums["received"],
        "issued_30d": abs(sums["issued"]),
        "adjusted_30d": sums["adjusted"],
        "activity_events": events,
        "activity_page": activity_page_obj,
        "gallery_images": list(ProductImage.objects.filter(product=product)),
        "custom_values": list(
            ProductCustomValue.objects.filter(product=product)
            .select_related("field")
            .order_by("field__name")
        ),
    }
