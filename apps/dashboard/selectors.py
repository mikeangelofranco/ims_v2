from dataclasses import dataclass
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce

from apps.inventory.models import Product, StockLevel, StockMovement


@dataclass(frozen=True)
class DashboardSnapshot:
    total_products: int
    tracked_product_count: int
    low_stock_count: int
    out_of_stock_count: int
    in_stock_count: int
    inventory_value: Decimal
    stock_health: int
    in_stock_percent: int
    low_stock_percent: int
    out_of_stock_percent: int
    low_stock_items: tuple
    recent_movements: tuple


def _percent(value, total):
    return round((value / total) * 100) if total else 0


def get_dashboard_snapshot():
    products = Product.objects.filter(is_active=True).annotate(
        total_quantity=Coalesce(Sum("stock_levels__quantity"), Value(0)),
        total_minimum=Coalesce(Sum("stock_levels__minimum_quantity"), Value(0)),
    )
    total_products = products.count()
    out_of_stock_count = products.filter(track_inventory=True, total_quantity=0).count()
    low_stock_count = products.filter(
        track_inventory=True,
        total_quantity__gt=0,
        total_quantity__lte=F("total_minimum"),
    ).count()
    tracked_products = products.filter(track_inventory=True).count()
    in_stock_count = max(tracked_products - low_stock_count - out_of_stock_count, 0)
    inventory_expression = ExpressionWrapper(
        F("quantity") * F("product__unit_cost"),
        output_field=DecimalField(max_digits=20, decimal_places=2),
    )
    inventory_value = StockLevel.objects.aggregate(
        total=Coalesce(Sum(inventory_expression), Decimal("0"))
    )["total"]
    return DashboardSnapshot(
        total_products=total_products,
        tracked_product_count=tracked_products,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        in_stock_count=in_stock_count,
        inventory_value=inventory_value,
        stock_health=_percent(in_stock_count, tracked_products),
        in_stock_percent=_percent(in_stock_count, tracked_products),
        low_stock_percent=_percent(low_stock_count, tracked_products),
        out_of_stock_percent=_percent(out_of_stock_count, tracked_products),
        low_stock_items=tuple(
            StockLevel.objects.select_related("product", "location")
            .filter(
                quantity__gt=0,
                quantity__lte=F("minimum_quantity"),
                product__is_active=True,
                product__track_inventory=True,
            )
            .order_by("quantity", "product__name")[:5]
        ),
        recent_movements=tuple(
            StockMovement.objects.select_related("product", "actor").order_by("-created_at")[:4]
        ),
    )
