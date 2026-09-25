from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from django.db.models import DecimalField, ExpressionWrapper, F, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce

from .models import Product, StockLevel
from .selectors import product_inventory


@dataclass(frozen=True)
class InventoryReportSummary:
    total_products: int
    total_stock: int
    inventory_value: Decimal
    low_stock: int
    out_of_stock: int

    @property
    def stock_alerts(self):
        return self.low_stock + self.out_of_stock


REPORT_SORTS = {
    "name": "name",
    "sku": "sku",
    "category": "category__name",
    "stock": "total_quantity",
    "minimum": "total_minimum",
    "status": "stock_status",
    "value": "report_value",
}


def _uuid(value):
    try:
        return UUID(value) if value else None
    except (TypeError, ValueError, AttributeError):
        return False


def inventory_report_summary():
    products = product_inventory()
    value_expression = ExpressionWrapper(
        F("quantity") * F("product__selling_price"),
        output_field=DecimalField(max_digits=24, decimal_places=2),
    )
    inventory_value = StockLevel.objects.aggregate(
        total=Coalesce(
            Sum(value_expression),
            Value(Decimal("0")),
            output_field=DecimalField(max_digits=24, decimal_places=2),
        )
    )["total"]
    return InventoryReportSummary(
        total_products=products.count(),
        total_stock=StockLevel.objects.aggregate(
            total=Coalesce(Sum("quantity"), Value(0))
        )["total"],
        inventory_value=inventory_value,
        low_stock=products.filter(stock_status="low").count(),
        out_of_stock=products.filter(stock_status="out").count(),
    )


def inventory_report_products(params):
    location_id = _uuid(params.get("location"))
    category_id = _uuid(params.get("category"))
    if location_id is False or category_id is False:
        return Product.objects.none()
    products = product_inventory(location_id).annotate(
        report_value=ExpressionWrapper(
            F("total_quantity") * F("selling_price"),
            output_field=DecimalField(max_digits=24, decimal_places=2),
        )
    )
    query = params.get("q", "").strip()[:200]
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(barcode__icontains=query)
        )
    if category_id:
        products = products.filter(category_id=category_id)
    status = params.get("status", "all")
    if status in {"in", "low", "out", "inactive", "untracked"}:
        products = products.filter(stock_status=status)
    stock_levels = StockLevel.objects.select_related("location").order_by("location__name")
    if location_id:
        stock_levels = stock_levels.filter(location_id=location_id)
    products = products.prefetch_related(
        Prefetch("stock_levels", queryset=stock_levels, to_attr="report_stock_levels")
    )
    sort = params.get("sort", "name")
    ordering = REPORT_SORTS.get(sort.lstrip("-"), "name")
    return products.order_by(("-" if sort.startswith("-") else "") + ordering, "pk")
