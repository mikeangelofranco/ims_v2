from django.db.models import Case, CharField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce

from .models import Product

SORTS = {
    "name": "name",
    "sku": "sku",
    "category": "category__name",
    "stock": "total_quantity",
    "minimum": "total_minimum",
    "price": "selling_price",
    "status": "stock_status",
    "updated": "updated_at",
}
STATUSES = (
    ("all", "All Products"),
    ("in", "In Stock"),
    ("low", "Low Stock"),
    ("out", "Out of Stock"),
    ("inactive", "Inactive"),
)


def product_inventory(location_id=None):
    products = Product.objects.select_related("category", "updated_by")
    if location_id:
        products = products.filter(stock_levels__location_id=location_id)
    return products.annotate(
        total_quantity=Coalesce(Sum("stock_levels__quantity"), Value(0)),
        total_minimum=Coalesce(Sum("stock_levels__minimum_quantity"), Value(0)),
    ).annotate(
        stock_status=Case(
            When(is_active=False, then=Value("inactive")),
            When(track_inventory=False, then=Value("untracked")),
            When(total_quantity=0, then=Value("out")),
            When(total_quantity__lte=F("total_minimum"), then=Value("low")),
            default=Value("in"),
            output_field=CharField(),
        )
    )


def filtered_products(params):
    from uuid import UUID

    location = params.get("location", "")
    try:
        location_id = UUID(location) if location else None
    except ValueError, TypeError, AttributeError:
        return Product.objects.none()
    products = product_inventory(location_id)
    query = params.get("q", "").strip()[:200]
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(barcode__icontains=query)
            | Q(category__name__icontains=query)
        )
    category = params.get("category", "")
    if category:
        if category == "uncategorized":
            products = products.filter(category__isnull=True)
            category = ""
        # UUID validation avoids database errors for malformed request values.
        from uuid import UUID

        if category:
            try:
                products = products.filter(category_id=UUID(category))
            except ValueError, TypeError, AttributeError:
                products = products.none()
    status = params.get("status", "all")
    if status in dict(STATUSES) and status != "all":
        products = products.filter(stock_status=status)
    sort = params.get("sort", "name")
    field = SORTS.get(sort.lstrip("-"), "name")
    return products.order_by(("-" if sort.startswith("-") else "") + field, "pk")


def product_counts():
    products = product_inventory()
    counts = {key: products.filter(stock_status=key).count() for key, _ in STATUSES if key != "all"}
    counts["all"] = products.count()
    return counts
