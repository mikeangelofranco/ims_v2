import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from apps.tenancy.middleware import TenantAccessMiddleware, TenantResolutionMiddleware
from apps.tenancy.models import Tenant, TenantDomain, TenantMembership


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
def test_authenticated_user_requires_active_membership():
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    user = get_user_model().objects.create_user(email="user@example.com", password="irrelevant")
    request = RequestFactory().get("/")
    request.tenant = tenant
    request.user = user

    denied = TenantAccessMiddleware(lambda _request: HttpResponse("ok"))(request)
    TenantMembership.objects.create(tenant=tenant, user=user)
    allowed = TenantAccessMiddleware(lambda _request: HttpResponse("ok"))(request)

    assert denied.status_code == 403
    assert allowed.status_code == 200
