from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.http import HttpResponseForbidden, HttpResponseNotFound

from .context import tenant_context
from .models import TenantDomain, TenantMembership, TenantStatus


def _request_hostname(request):
    host = request.get_host().strip().rstrip(".").lower()
    try:
        parsed = urlsplit(f"//{host}")
        hostname = parsed.hostname
        _port = parsed.port
    except ValueError as exc:
        raise DisallowedHost("Invalid host header.") from exc
    return hostname or host


class TenantResolutionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in settings.TENANCY_EXEMPT_PATHS:
            request.tenant = None
            return self.get_response(request)

        hostname = _request_hostname(request)
        domain = (
            TenantDomain.objects.select_related("tenant")
            .filter(
                hostname=hostname,
                is_active=True,
                tenant__status=TenantStatus.ACTIVE,
            )
            .first()
        )
        if domain is None:
            return HttpResponseNotFound("Tenant not found.")

        request.tenant = domain.tenant
        with tenant_context(domain.tenant):
            return self.get_response(request)


class TenantAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is not None and request.user.is_authenticated:
            has_access = TenantMembership.objects.filter(
                tenant=tenant,
                user=request.user,
                is_active=True,
            ).exists()
            if not has_access:
                return HttpResponseForbidden("You do not have access to this tenant.")
        return self.get_response(request)
