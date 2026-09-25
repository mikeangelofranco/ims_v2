import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from apps.tenancy.middleware import TenantAccessMiddleware, TenantResolutionMiddleware
from apps.tenancy.models import Tenant, TenantDomain, TenantMembership, TenantStatus


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["acme.localhost", "unknown.localhost"], TENANCY_EXEMPT_PATHS=())
def test_resolution_uses_exact_active_domain():
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    TenantDomain.objects.create(tenant=tenant, hostname="acme.localhost", is_primary=True)
    request = RequestFactory().get("/private/", HTTP_HOST="acme.localhost")

    response = TenantResolutionMiddleware(lambda req: HttpResponse(str(req.tenant.id)))(request)

    assert response.status_code == 200
    assert response.content.decode() == str(tenant.id)


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["unknown.localhost"], TENANCY_EXEMPT_PATHS=())
def test_unknown_domain_returns_not_found():
    request = RequestFactory().get("/private/", HTTP_HOST="unknown.localhost")
    response = TenantResolutionMiddleware(lambda _request: HttpResponse("unsafe"))(request)
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("inactive_target", ["domain", "tenant"])
@override_settings(ALLOWED_HOSTS=["acme.localhost"], TENANCY_EXEMPT_PATHS=())
def test_inactive_tenant_or_domain_returns_not_found(inactive_target):
    tenant = Tenant.objects.create(
        name="Acme",
        slug="acme",
        status=(
            TenantStatus.SUSPENDED if inactive_target == "tenant" else TenantStatus.ACTIVE
        ),
    )
    TenantDomain.objects.create(
        tenant=tenant,
        hostname="acme.localhost",
        is_primary=True,
        is_active=inactive_target != "domain",
    )
    request = RequestFactory().get("/app/", HTTP_HOST="acme.localhost")

    response = TenantResolutionMiddleware(lambda _request: HttpResponse("unsafe"))(request)

    assert response.status_code == 404


@pytest.mark.django_db
def test_authenticated_user_requires_active_membership():
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    user = get_user_model().objects.create_user(email="user@example.com", password="irrelevant")
    request = RequestFactory().get("/app/")
    request.tenant = tenant
    request.user = user

    denied = TenantAccessMiddleware(lambda _request: HttpResponse("ok"))(request)
    TenantMembership.objects.create(tenant=tenant, user=user)
    allowed = TenantAccessMiddleware(lambda _request: HttpResponse("ok"))(request)

    assert denied.status_code == 403
    assert allowed.status_code == 200


@pytest.mark.django_db
@override_settings(
    ALLOWED_HOSTS=["localhost", "unknown.localhost"],
    TENANCY_PLATFORM_HOSTS=("localhost",),
)
def test_public_paths_are_only_exempt_on_configured_platform_hosts():
    platform_request = RequestFactory().get("/sign-in/", HTTP_HOST="localhost")
    unknown_request = RequestFactory().get("/sign-in/", HTTP_HOST="unknown.localhost")
    middleware = TenantResolutionMiddleware(lambda _request: HttpResponse("ok"))

    platform_response = middleware(platform_request)
    unknown_response = middleware(unknown_request)

    assert platform_response.status_code == 200
    assert platform_request.tenant is None
    assert unknown_response.status_code == 404


@pytest.mark.django_db
def test_tenant_access_defaults_to_login_and_denies_platform_only_paths():
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    user = get_user_model().objects.create_user(email="user@example.com", password="irrelevant")
    TenantMembership.objects.create(tenant=tenant, user=user)
    middleware = TenantAccessMiddleware(lambda _request: HttpResponse("ok"))

    anonymous_request = RequestFactory().get("/app/?view=stock")
    anonymous_request.tenant = tenant
    anonymous_request.user = AnonymousUser()
    anonymous_response = middleware(anonymous_request)

    platform_path_request = RequestFactory().get("/register/ready/")
    platform_path_request.tenant = tenant
    platform_path_request.user = user
    platform_path_response = middleware(platform_path_request)

    assert anonymous_response.status_code == 302
    assert anonymous_response.url == "/sign-in/?next=%2Fapp%2F%3Fview%3Dstock"
    assert platform_path_response.status_code == 404
