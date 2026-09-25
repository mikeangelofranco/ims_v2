import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from apps.businesses.models import BusinessProfile
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Tenant, TenantDomain, TenantMembership, TenantRole

User = get_user_model()


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["acme.localhost"], TENANCY_EXEMPT_PATHS=())
def test_dashboard_renders_tenant_business_and_empty_inventory(client):
    tenant = Tenant.objects.create(name="Acme Workspace", slug="acme")
    TenantDomain.objects.create(tenant=tenant, hostname="acme.localhost", is_primary=True)
    user = User.objects.create_user(
        email="owner@acme.example",
        password="StrongPass1!",
        first_name="Mika",
    )
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    with tenant_context(tenant):
        BusinessProfile.objects.create(
            legal_name="Acme Trading Corporation",
            industry="wholesale",
            company_size="11-50",
        )
    client.force_login(user)

    response = client.get(reverse("onboarding:workspace_home"), HTTP_HOST="acme.localhost")

    assert response.status_code == 200
    assert b"Overview of your inventory at a glance" in response.content
    assert b'class="app-dashboard-shell"' in response.content
    assert b'class="dashboard-shell"' not in response.content
    assert b"Acme Workspace" in response.content
    assert b"acme.plughubcore.com" in response.content
    assert b"No low-stock items" in response.content
    assert b"No inventory activity yet" in response.content
    assert b'class="low-stock dashboard-card is-empty"' in response.content
    assert b'class="recent-activity dashboard-card is-empty"' in response.content
    assert f'action="{reverse("onboarding:sign_out")}"'.encode() in response.content
    assert b">Log out<" in response.content
    assert b'aria-label="Notifications"' not in response.content
    assert b'data-lucide="bell"' not in response.content


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["acme.localhost"], TENANCY_EXEMPT_PATHS=())
def test_dashboard_requires_active_tenant_membership(client):
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    TenantDomain.objects.create(tenant=tenant, hostname="acme.localhost", is_primary=True)
    user = User.objects.create_user(email="outsider@example.com", password="StrongPass1!")
    client.force_login(user)

    response = client.get(reverse("onboarding:workspace_home"), HTTP_HOST="acme.localhost")

    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["acme.localhost"], TENANCY_EXEMPT_PATHS=())
def test_logout_is_post_only_and_clears_tenant_session(client):
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    TenantDomain.objects.create(tenant=tenant, hostname="acme.localhost", is_primary=True)
    user = User.objects.create_user(email="owner@example.com", password="StrongPass1!")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    client.force_login(user)

    get_response = client.get(reverse("onboarding:sign_out"), HTTP_HOST="acme.localhost")
    post_response = client.post(reverse("onboarding:sign_out"), HTTP_HOST="acme.localhost")
    protected_response = client.get(
        reverse("onboarding:workspace_home"), HTTP_HOST="acme.localhost"
    )

    assert get_response.status_code == 405
    assert post_response.status_code == 302
    assert post_response.url == reverse("onboarding:sign_in")
    assert "_auth_user_id" not in client.session
    assert protected_response.status_code == 302
    assert protected_response.url == "/sign-in/?next=%2Fapp%2F"


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["acme.localhost"], TENANCY_EXEMPT_PATHS=())
def test_logout_requires_csrf_token():
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    TenantDomain.objects.create(tenant=tenant, hostname="acme.localhost", is_primary=True)
    user = User.objects.create_user(email="owner@example.com", password="StrongPass1!")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)

    response = csrf_client.post(reverse("onboarding:sign_out"), HTTP_HOST="acme.localhost")

    assert response.status_code == 403
    assert csrf_client.session["_auth_user_id"] == str(user.pk)
