from urllib.parse import urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from apps.businesses.models import BusinessProfile
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Tenant, TenantDomain, TenantMembership, TenantRole

User = get_user_model()


@pytest.mark.django_db
@override_settings(DEBUG=True, CSRF_COOKIE_NAME="coreflow_dev_csrftoken")
def test_missing_local_csrf_cookie_reloads_form_without_authenticating():
    client = Client(enforce_csrf_checks=True)
    response = client.post(
        reverse("onboarding:sign_in"),
        {"email": "local@example.com", "password": "StrongPass1!"},
    )
    assert response.status_code == 302
    assert response.url == "/sign-in/?csrf_retry=1"
    assert "_auth_user_id" not in client.session
    fresh_form = client.get(response.url)
    assert fresh_form.status_code == 200
    assert b"form was out of date" in fresh_form.content
    assert "coreflow_dev_csrftoken" in fresh_form.cookies
    assert fresh_form.cookies["coreflow_dev_csrftoken"]["domain"] == ""


@pytest.mark.django_db
def test_login_with_real_csrf_validation_and_origin_checks():
    user = User.objects.create_user(email="csrf@example.com", password="StrongPass1!")
    client = Client(enforce_csrf_checks=True)
    page = client.get(reverse("onboarding:sign_in"))
    token = page.cookies["csrftoken"].value
    data = {
        "email": user.email,
        "password": "StrongPass1!",
        "csrfmiddlewaretoken": token,
    }
    rejected = client.post(
        reverse("onboarding:sign_in"), data, HTTP_ORIGIN="https://attacker.example"
    )
    assert rejected.status_code == 403
    assert "_auth_user_id" not in client.session
    accepted = client.post(reverse("onboarding:sign_in"), data)
    assert accepted.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
@override_settings(
    SESSION_COOKIE_NAME="coreflow_dev_sessionid",
    CSRF_COOKIE_NAME="coreflow_dev_csrftoken",
)
def test_local_login_ignores_legacy_project_cookies(client):
    user = User.objects.create_user(email="local@example.com", password="StrongPass1!")
    client.cookies["sessionid"] = "stale-session-from-another-project"
    client.cookies["csrftoken"] = "stale-csrf-from-another-project"

    response = client.post(
        reverse("onboarding:sign_in"),
        {"email": user.email, "password": "StrongPass1!"},
    )

    assert response.status_code == 302
    assert response.url == reverse("onboarding:workspace")
    assert "coreflow_dev_sessionid" in response.cookies
    assert response.cookies["coreflow_dev_sessionid"]["domain"] == ""
    assert client.session["_auth_user_id"] == str(user.pk)
    assert client.get(response.url).status_code == 200


@pytest.mark.django_db
def test_account_page_matches_registration_structure(client):
    response = client.get(reverse("onboarding:account"))

    assert response.status_code == 200
    assert b"Create your CoreFlow account." in response.content
    assert b"registration-progress" in response.content
    assert b"industry-standard encryption" in response.content


@pytest.mark.django_db
def test_account_creation_hashes_password_and_signs_user_in(client):
    response = client.post(
        reverse("onboarding:account"),
        {
            "first_name": "Mika",
            "email": "MIKA@example.com",
            "password": "StrongPass1!",
        },
    )

    user = User.objects.get(email="mika@example.com")
    assert response.status_code == 302
    assert response.url == reverse("onboarding:workspace")
    assert user.first_name == "Mika"
    assert user.check_password("StrongPass1!")
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_account_creation_rejects_duplicate_email_and_weak_password(client):
    User.objects.create_user(email="existing@example.com", password="Existing1!")

    response = client.post(
        reverse("onboarding:account"),
        {
            "first_name": "Mika",
            "email": "Existing@example.com",
            "password": "onlyletters",
        },
    )

    assert response.status_code == 200
    assert b"already exists" in response.content
    assert b"Add at least one number" in response.content
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_complete_registration_creates_tenant_membership_domain_and_business(client):
    client.post(
        reverse("onboarding:account"),
        {
            "first_name": "Mika",
            "email": "mika@example.com",
            "password": "StrongPass1!",
        },
    )

    workspace_response = client.post(
        reverse("onboarding:workspace"),
        {
            "workspace_name": "Acme Operations",
            "workspace_slug": "acme",
            "timezone": "Asia/Manila",
        },
    )
    tenant = Tenant.objects.get(slug="acme")
    user = User.objects.get(email="mika@example.com")

    assert workspace_response.status_code == 302
    assert workspace_response.url == reverse("onboarding:business")
    assert tenant.timezone == "Asia/Manila"
    assert TenantDomain.objects.filter(
        tenant=tenant,
        hostname="acme.localhost",
        is_primary=True,
    ).exists()
    assert TenantMembership.objects.filter(
        tenant=tenant,
        user=user,
        role=TenantRole.OWNER,
        is_active=True,
    ).exists()

    business_response = client.post(
        reverse("onboarding:business"),
        {
            "legal_name": "Acme Trading Inc.",
            "industry": "wholesale",
            "company_size": "2-10",
            "currency": "PHP",
            "timezone": "Asia/Singapore",
            "business_email": "billing@acme.example",
            "address": "123 Commerce Street",
            "tax_identifier": "TIN-100200",
            "registration_number": "REG-900100",
        },
    )

    assert business_response.status_code == 302
    assert business_response.url == reverse("onboarding:ready")
    with tenant_context(tenant):
        profile = BusinessProfile.objects.get()
    assert profile.legal_name == "Acme Trading Inc."
    assert profile.currency == "PHP"
    assert profile.business_email == "billing@acme.example"
    assert profile.address == "123 Commerce Street"
    assert profile.tax_identifier == "TIN-100200"
    assert profile.registration_number == "REG-900100"
    tenant.refresh_from_db()
    assert tenant.timezone == "Asia/Singapore"

    ready_response = client.get(reverse("onboarding:ready"))
    assert ready_response.status_code == 200
    assert b"Everything is ready!" in ready_response.content
    assert b"Acme Trading Inc." in ready_response.content
    assert b"Trading / Wholesale" in ready_response.content
    assert b"2 \xe2\x80\x93 10 employees" in ready_response.content
    assert b"acme.plughubcore.com" in ready_response.content
    assert b"Asia/Singapore (GMT+08:00)" in ready_response.content
    assert reverse("onboarding:launch_workspace").encode() in ready_response.content
    assert b'data-lucide="user-round"' in ready_response.content
    assert b'data-lucide="building-2"' in ready_response.content
    assert b'data-lucide="store"' in ready_response.content
    assert "👋".encode() not in ready_response.content


@pytest.mark.django_db
def test_ready_page_launches_an_authenticated_tenant_workspace(client):
    user = User.objects.create_user(email="launch@example.com", password="StrongPass1!")
    tenant = Tenant.objects.create(name="Launch", slug="launch")
    TenantDomain.objects.create(tenant=tenant, hostname="launch.localhost", is_primary=True)
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    with tenant_context(tenant):
        BusinessProfile.objects.create(
            legal_name="Launch Inc.",
            industry="services",
            company_size="solo",
        )
    client.force_login(user)

    launch_response = client.get(reverse("onboarding:launch_workspace"))

    assert launch_response.status_code == 302
    destination = urlsplit(launch_response.url)
    assert destination.hostname == "launch.localhost"
    assert destination.path == reverse("onboarding:workspace_session")
    assert client.session["_auth_user_id"] == str(user.pk)

    tenant_client = Client()
    handoff_response = tenant_client.get(
        f"{destination.path}?{destination.query}",
        HTTP_HOST="launch.localhost",
    )
    assert handoff_response.status_code == 302
    assert handoff_response.url == reverse("onboarding:workspace_home")
    assert tenant_client.session["_auth_user_id"] == str(user.pk)

    dashboard_response = tenant_client.get(
        reverse("onboarding:workspace_home"),
        HTTP_HOST="launch.localhost",
    )
    assert dashboard_response.status_code == 200
    assert b"Overview of your inventory at a glance" in dashboard_response.content

    tenant_client.post(reverse("onboarding:sign_out"), HTTP_HOST="launch.localhost")
    replay_response = tenant_client.get(
        f"{destination.path}?{destination.query}",
        HTTP_HOST="launch.localhost",
    )
    assert replay_response.status_code == 302
    assert replay_response.url == reverse("onboarding:sign_in")
    assert "_auth_user_id" not in tenant_client.session


@pytest.mark.django_db
def test_ready_page_redirects_until_business_profile_exists(client):
    user = User.objects.create_user(email="not-ready@example.com", password="StrongPass1!")
    tenant = Tenant.objects.create(name="Not Ready", slug="not-ready")
    TenantDomain.objects.create(tenant=tenant, hostname="not-ready.localhost", is_primary=True)
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    client.force_login(user)

    response = client.get(reverse("onboarding:ready"))

    assert response.status_code == 302
    assert response.url == reverse("onboarding:business")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("next_url", "expected_url"),
    [
        ("/app/?view=stock", "/app/?view=stock"),
        ("https://attacker.example/steal", "/app/"),
    ],
)
def test_tenant_sign_in_requires_membership_and_uses_safe_redirect(client, next_url, expected_url):
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    TenantDomain.objects.create(tenant=tenant, hostname="acme.localhost", is_primary=True)
    member = User.objects.create_user(email="member@example.com", password="StrongPass1!")
    TenantMembership.objects.create(tenant=tenant, user=member, role=TenantRole.OWNER)

    response = client.post(
        reverse("onboarding:sign_in"),
        {"email": member.email, "password": "StrongPass1!", "next": next_url},
        HTTP_HOST="acme.localhost",
    )

    assert response.status_code == 302
    assert response.url == expected_url
    assert client.session["_auth_user_id"] == str(member.pk)


@pytest.mark.django_db
def test_tenant_sign_in_rejects_valid_credentials_without_membership(client):
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    TenantDomain.objects.create(tenant=tenant, hostname="acme.localhost", is_primary=True)
    outsider = User.objects.create_user(email="outsider@example.com", password="StrongPass1!")

    response = client.post(
        reverse("onboarding:sign_in"),
        {"email": outsider.email, "password": "StrongPass1!"},
        HTTP_HOST="acme.localhost",
    )

    assert response.status_code == 200
    assert b"The email address or password is incorrect." in response.content
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_registration_resumes_at_first_incomplete_stage(client):
    user = User.objects.create_user(email="resume@example.com", password="StrongPass1!")
    client.force_login(user)

    response = client.get(reverse("onboarding:account"))

    assert response.status_code == 302
    assert response.url == reverse("onboarding:workspace")


@pytest.mark.django_db
def test_workspace_page_includes_live_slug_check_and_persisted_settings(client):
    user = User.objects.create_user(email="workspace@example.com", password="StrongPass1!")
    client.force_login(user)

    response = client.get(reverse("onboarding:workspace"))

    assert response.status_code == 200
    assert b'hx-get="/register/workspace/check-slug/"' in response.content
    assert b".plughubcore.com" in response.content
    assert b"Workspace logo (optional)" in response.content


@pytest.mark.django_db
def test_workspace_slug_availability_checks_tenant_and_domain_records(client):
    user = User.objects.create_user(email="availability@example.com", password="StrongPass1!")
    client.force_login(user)
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    TenantDomain.objects.create(tenant=tenant, hostname="acme.localhost", is_primary=True)

    unavailable = client.get(
        reverse("onboarding:check_workspace_slug"),
        {"workspace_slug": "acme"},
    )
    available = client.get(
        reverse("onboarding:check_workspace_slug"),
        {"workspace_slug": "north-star"},
    )

    assert b"already taken" in unavailable.content
    assert b"Available" in available.content
    assert b"north-star</b>.plughubcore.com" in available.content


@pytest.mark.django_db
def test_workspace_rejects_unsafe_svg_logo(client):
    user = User.objects.create_user(email="logo@example.com", password="StrongPass1!")
    client.force_login(user)
    unsafe_logo = SimpleUploadedFile(
        "logo.svg",
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        content_type="image/svg+xml",
    )

    response = client.post(
        reverse("onboarding:workspace"),
        {
            "workspace_name": "Safe Workspace",
            "workspace_slug": "safe-workspace",
            "timezone": "Asia/Manila",
            "logo": unsafe_logo,
        },
    )

    assert response.status_code == 200
    assert b"unsafe content" in response.content
    assert not Tenant.objects.filter(slug="safe-workspace").exists()


@pytest.mark.django_db
def test_business_page_has_live_preview_and_persisted_fields(client):
    user = User.objects.create_user(email="business@example.com", password="StrongPass1!")
    tenant = Tenant.objects.create(name="Acme Trading", slug="acme-trading")
    TenantDomain.objects.create(tenant=tenant, hostname="acme-trading.localhost", is_primary=True)
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    client.force_login(user)

    response = client.get(reverse("onboarding:business"))

    assert response.status_code == 200
    assert b"Create your business." in response.content
    assert b"data-business-form" in response.content
    assert b"Additional details" in response.content
    assert b"Business preview" in response.content
    assert b"acme-trading.plughubcore.com" in response.content


@pytest.mark.django_db
def test_business_rejects_invalid_email_without_creating_profile(client):
    user = User.objects.create_user(email="owner@example.com", password="StrongPass1!")
    tenant = Tenant.objects.create(name="Owner Co", slug="owner-co")
    TenantDomain.objects.create(tenant=tenant, hostname="owner-co.localhost", is_primary=True)
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    client.force_login(user)

    response = client.post(
        reverse("onboarding:business"),
        {
            "legal_name": "Owner Co",
            "industry": "services",
            "company_size": "solo",
            "currency": "PHP",
            "timezone": "Asia/Manila",
            "business_email": "not-an-email",
        },
    )

    assert response.status_code == 200
    assert b"Enter a valid email address" in response.content
    with tenant_context(tenant):
        assert not BusinessProfile.objects.exists()


@pytest.mark.django_db
def test_back_path_updates_existing_workspace_without_duplication(client):
    user = User.objects.create_user(email="edit-workspace@example.com", password="StrongPass1!")
    tenant = Tenant.objects.create(name="Before", slug="before", timezone="Asia/Manila")
    TenantDomain.objects.create(tenant=tenant, hostname="before.localhost", is_primary=True)
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    client.force_login(user)

    availability = client.get(
        reverse("onboarding:check_workspace_slug"),
        {"workspace_slug": "before"},
    )
    assert b"Available" in availability.content

    response = client.post(
        f"{reverse('onboarding:workspace')}?edit=1",
        {
            "workspace_name": "After",
            "workspace_slug": "after",
            "timezone": "Asia/Tokyo",
        },
    )

    tenant.refresh_from_db()
    assert response.status_code == 302
    assert response.url == reverse("onboarding:business")
    assert Tenant.objects.count() == 1
    assert tenant.name == "After"
    assert tenant.slug == "after"
    assert tenant.timezone == "Asia/Tokyo"
    assert tenant.domains.get(is_primary=True).hostname == "after.localhost"


@pytest.mark.django_db
def test_workspace_edit_displays_and_preserves_existing_logo(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    user = User.objects.create_user(email="logo-owner@example.com", password="StrongPass1!")
    client.force_login(user)
    logo = SimpleUploadedFile(
        "workspace.png",
        b"\x89PNG\r\n\x1a\nexisting-logo",
        content_type="image/png",
    )
    client.post(
        reverse("onboarding:workspace"),
        {
            "workspace_name": "Logo Workspace",
            "workspace_slug": "logo-workspace",
            "timezone": "Asia/Manila",
            "logo": logo,
        },
    )
    tenant = Tenant.objects.get(slug="logo-workspace")
    original_logo_name = tenant.logo.name
    logo_url = reverse("onboarding:workspace_logo", args=[tenant.pk])

    edit_page = client.get(f"{reverse('onboarding:workspace')}?edit=1")
    logo_response = client.get(logo_url)
    response = client.post(
        f"{reverse('onboarding:workspace')}?edit=1",
        {
            "workspace_name": "Logo Workspace Updated",
            "workspace_slug": "logo-workspace",
            "timezone": "Asia/Manila",
        },
    )

    tenant.refresh_from_db()
    assert edit_page.status_code == 200
    assert logo_url.encode() in edit_page.content
    assert logo_response.status_code == 200
    assert logo_response["Content-Type"] == "image/png"
    assert b"".join(logo_response.streaming_content).startswith(b"\x89PNG")
    assert b"Change logo" in edit_page.content
    assert response.status_code == 302
    assert response.url == reverse("onboarding:business")
    assert tenant.logo.name == original_logo_name
    assert tenant.logo.storage.exists(original_logo_name)

    outsider = User.objects.create_user(email="logo-outsider@example.com", password="StrongPass1!")
    client.force_login(outsider)
    assert client.get(logo_url).status_code == 404


@pytest.mark.django_db
def test_workspace_logo_cannot_cross_the_resolved_tenant_boundary(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    user = User.objects.create_user(email="multi-owner@example.com", password="StrongPass1!")
    first = Tenant.objects.create(
        name="First",
        slug="first",
        logo=SimpleUploadedFile("first.png", b"\x89PNG\r\n\x1a\nfirst", "image/png"),
    )
    second = Tenant.objects.create(name="Second", slug="second")
    TenantDomain.objects.create(tenant=first, hostname="first.localhost", is_primary=True)
    TenantDomain.objects.create(tenant=second, hostname="second.localhost", is_primary=True)
    TenantMembership.objects.create(tenant=first, user=user, role=TenantRole.OWNER)
    TenantMembership.objects.create(tenant=second, user=user, role=TenantRole.OWNER)
    client.force_login(user)

    response = client.get(
        reverse("onboarding:workspace_logo", args=[first.pk]),
        HTTP_HOST="second.localhost",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_back_path_updates_account_without_requiring_a_new_password(client):
    user = User.objects.create_user(
        email="before@example.com",
        password="StrongPass1!",
        first_name="Before",
    )
    client.force_login(user)

    response = client.post(
        f"{reverse('onboarding:account')}?edit=1",
        {"first_name": "After", "email": "after@example.com", "password": ""},
    )

    user.refresh_from_db()
    assert response.status_code == 302
    assert response.url == reverse("onboarding:workspace")
    assert user.first_name == "After"
    assert user.email == "after@example.com"
    assert user.check_password("StrongPass1!")


@pytest.mark.django_db
def test_workspace_home_requires_matching_tenant_membership(client):
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    TenantDomain.objects.create(tenant=tenant, hostname="acme.localhost", is_primary=True)
    user = User.objects.create_user(email="owner@example.com", password="StrongPass1!")
    TenantMembership.objects.create(
        tenant=tenant,
        user=user,
        role=TenantRole.OWNER,
    )
    with tenant_context(tenant):
        BusinessProfile.objects.create(
            legal_name="Acme Inc.",
            industry="retail",
            company_size="solo",
        )
    client.force_login(user)

    response = client.get(reverse("onboarding:workspace_home"), HTTP_HOST="acme.localhost")

    assert response.status_code == 200
    assert b"Overview of your inventory at a glance" in response.content


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("destination_key", "route"),
    [
        ("products", "inventory:product_list"),
        ("add-product", "inventory:product_create"),
        ("import-products", "inventory:product_import"),
        ("https://other.localhost/app/products/", "onboarding:workspace_home"),
    ],
)
def test_product_shortcuts_handoff_to_owned_workspace(client, destination_key, route):
    user = User.objects.create_user(email="shortcut@example.com", password="StrongPass1!")
    tenant = Tenant.objects.create(name="Shortcut", slug="shortcut")
    TenantDomain.objects.create(tenant=tenant, hostname="shortcut.localhost", is_primary=True)
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    with tenant_context(tenant):
        BusinessProfile.objects.create(
            legal_name="Shortcut Inc.", industry="retail", company_size="solo"
        )
    client.force_login(user)
    ready = client.get(reverse("onboarding:ready"))
    assert b'href="/launch-workspace/?destination=add-product"' in ready.content
    assert b'href="/launch-workspace/?destination=import-products"' in ready.content
    launch = client.get(reverse("onboarding:launch_workspace"), {"destination": destination_key})
    destination = urlsplit(launch.url)
    assert destination.hostname == "shortcut.localhost"
    tenant_client = Client()
    handoff = tenant_client.get(
        f"{destination.path}?{destination.query}", HTTP_HOST="shortcut.localhost"
    )
    assert handoff.status_code == 302
    assert handoff.url == reverse(route)
    assert tenant_client.get(handoff.url, HTTP_HOST="shortcut.localhost").status_code == 200
