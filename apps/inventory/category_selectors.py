from django.db.models import Count, Q

from .models import Category, Product

CATEGORY_SORTS = {
    "name": "name",
    "description": "description",
    "products": "product_count",
    "status": "is_active",
    "updated": "updated_at",
}


def category_summary():
    return {
        "total_categories": Category.objects.count(),
        "active_categories": Category.objects.filter(is_active=True).count(),
        "uncategorized_products": Product.objects.filter(category__isnull=True).count(),
    }


def filtered_categories(params):
    categories = Category.objects.select_related("updated_by").annotate(
        product_count=Count("products")
    )
    query = params.get("q", "").strip()[:200]
    if query:
        categories = categories.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(description__icontains=query)
        )
    status = params.get("status", "all")
    if status == "active":
        categories = categories.filter(is_active=True)
    elif status == "inactive":
        categories = categories.filter(is_active=False)
    sort = params.get("sort", "name")
    field = CATEGORY_SORTS.get(sort.lstrip("-"), "name")
    return categories.order_by(("-" if sort.startswith("-") else "") + field, "pk")
