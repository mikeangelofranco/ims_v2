from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.tenancy.context import tenant_context
from apps.tenancy.models import (
    Tenant,
    TenantMembership,
    TenantRole,
    WorkspaceSessionGrant,
)
from apps.tenancy.services import (
    issue_workspace_session_grant,
    redeem_workspace_session_grant,
)

User = get_user_model()


@pytest.mark.django_db
def test_workspace_session_grant_is_single_use_and_tenant_scoped():
    user = User.objects.create_user(email="member@example.com", password="StrongPass1!")
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    other_tenant = Tenant.objects.create(name="Other", slug="other")
    TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    TenantMembership.objects.create(tenant=other_tenant, user=user, role=TenantRole.OWNER)

    token = issue_workspace_session_grant(tenant=tenant, user=user)

    assert redeem_workspace_session_grant(tenant=other_tenant, token=token) is None
    assert redeem_workspace_session_grant(tenant=tenant, token=token) == user
    assert redeem_workspace_session_grant(tenant=tenant, token=token) is None


@pytest.mark.django_db
def test_workspace_session_grant_rejects_expired_or_inactive_access():
    user = User.objects.create_user(email="member@example.com", password="StrongPass1!")
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    membership = TenantMembership.objects.create(
        tenant=tenant,
        user=user,
        role=TenantRole.OWNER,
    )
    token = issue_workspace_session_grant(tenant=tenant, user=user)
    with tenant_context(tenant):
        WorkspaceSessionGrant.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

    assert redeem_workspace_session_grant(tenant=tenant, token=token) is None

    token = issue_workspace_session_grant(tenant=tenant, user=user)
    membership.is_active = False
    membership.save(update_fields=["is_active", "updated_at"])
    assert redeem_workspace_session_grant(tenant=tenant, token=token) is None
