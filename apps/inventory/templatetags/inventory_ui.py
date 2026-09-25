from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def product_query(context, **changes):
    query = context["request"].GET.copy()
    query.pop("append", None)
    for key, value in changes.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = str(value)
    return "?" + query.urlencode()


@register.simple_tag(takes_context=True)
def movement_query(context, **changes):
    query = context["request"].GET.copy()
    query.pop("action", None)
    for key, value in changes.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = str(value)
    encoded = query.urlencode()
    return "?" + encoded if encoded else "?"


@register.simple_tag(takes_context=True)
def report_query(context, **changes):
    query = context["request"].GET.copy()
    for key, value in changes.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = str(value)
    encoded = query.urlencode()
    return "?" + encoded if encoded else "?"


@register.filter
def stock_label(value):
    return {
        "in": "In Stock",
        "low": "Low Stock",
        "out": "Out of Stock",
        "inactive": "Inactive",
        "untracked": "Not tracked",
    }.get(value, value)


@register.filter
def abs_value(value):
    try:
        return abs(value)
    except (TypeError, ValueError):
        return value
