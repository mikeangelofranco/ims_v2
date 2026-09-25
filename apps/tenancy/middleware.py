from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import redirect
from django.urls import reverse

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
        hostname = _request_hostname(request)
        exempt_prefixes = getattr(settings, "TENANCY_EXEMPT_PATH_PREFIXES", ())
        domain = (
            TenantDomain.objects.select_related("tenant")
            .filter(
                hostname=hostname,
                is_active=True,
                tenant__status=TenantStatus.ACTIVE,
            )
            .first()
        )
        if domain is not None:
            request.tenant = domain.tenant
            with tenant_context(domain.tenant):
                return self.get_response(request)

        is_exempt_path = request.path in settings.TENANCY_EXEMPT_PATHS or (
            exempt_prefixes and request.path.startswith(exempt_prefixes)
        )
        if hostname in settings.TENANCY_PLATFORM_HOSTS and is_exempt_path:
            request.tenant = None
            return self.get_response(request)
        return HttpResponseNotFound("Tenant not found.")


class TenantAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return self.get_response(request)

        public_paths = getattr(settings, "TENANCY_TENANT_PUBLIC_PATHS", ())
        tenant_prefixes = getattr(settings, "TENANCY_TENANT_PATH_PREFIXES", ())
        is_public_path = request.path in public_paths
        is_tenant_path = request.path == "/" or (
            tenant_prefixes and request.path.startswith(tenant_prefixes)
        )
        if not is_public_path and not is_tenant_path:
            return HttpResponseNotFound("Page not found.")

        if not request.user.is_authenticated:
            if is_public_path:
                return self.get_response(request)
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"{reverse('onboarding:sign_in')}?{query}")

        has_access = TenantMembership.objects.filter(
            tenant=tenant,
            user=request.user,
            is_active=True,
        ).exists()
        if not has_access:
            return HttpResponseForbidden("You do not have access to this tenant.")
        if request.path == "/":
            return redirect("onboarding:workspace_home")
        return self.get_response(request)
