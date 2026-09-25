from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from apps.businesses.models import BusinessProfile
from apps.tenancy.models import TenantMembership

from .selectors import get_dashboard_snapshot


def _compact_currency(value, symbol):
    if value >= 1_000_000:
        return f"{symbol}{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{symbol}{value / 1_000:.1f}K"
    return f"{symbol}{value:,.0f}"


@login_required(login_url="/sign-in/")
@require_GET
def dashboard(request):
    if request.tenant is None:
        return redirect("onboarding:ready")
    business = BusinessProfile.objects.first()
    if business is None:
        return redirect("onboarding:business")
    membership = TenantMembership.objects.select_related("user").get(
        tenant=request.tenant,
        user=request.user,
        is_active=True,
    )
    snapshot = get_dashboard_snapshot()
    currency_symbol = "₱" if business.currency == "PHP" else f"{business.currency} "
    return render(
        request,
        "dashboard/dashboard.html",
        {
            "tenant": request.tenant,
            "business": business,
            "membership": membership,
            "snapshot": snapshot,
            "inventory_value": f"{currency_symbol}{snapshot.inventory_value:,.0f}",
            "inventory_value_compact": _compact_currency(snapshot.inventory_value, currency_symbol),
            "workspace_display_url": (f"{request.tenant.slug}.{settings.WORKSPACE_DISPLAY_DOMAIN}"),
        },
    )
