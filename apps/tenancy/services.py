import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .context import tenant_context
from .models import (
    TenantMembership,
    TenantStatus,
    WorkspaceSessionGrant,
)


def _token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@transaction.atomic
def issue_workspace_session_grant(*, tenant, user):
    has_access = TenantMembership.objects.filter(
        tenant=tenant,
        tenant__status=TenantStatus.ACTIVE,
        user=user,
        is_active=True,
    ).exists()
    if not has_access or not user.is_active:
        raise PermissionError("An active workspace membership is required.")

    token = secrets.token_urlsafe(32)
    expires_at = timezone.now() + timedelta(
        seconds=settings.WORKSPACE_SESSION_GRANT_TTL_SECONDS
    )
    with tenant_context(tenant):
        WorkspaceSessionGrant.objects.create(
            user=user,
            token_digest=_token_digest(token),
            expires_at=expires_at,
        )
    return token


@transaction.atomic
def redeem_workspace_session_grant(*, tenant, token):
    if not token:
        return None

    with tenant_context(tenant):
        grant = (
            WorkspaceSessionGrant.objects.select_for_update()
            .select_related("user")
            .filter(
                token_digest=_token_digest(token),
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if grant is None:
            return None

        grant.used_at = timezone.now()
        grant.save(update_fields=["used_at", "updated_at"])

    has_access = TenantMembership.objects.filter(
        tenant=tenant,
        tenant__status=TenantStatus.ACTIVE,
        user=grant.user,
        is_active=True,
    ).exists()
    if not has_access or not grant.user.is_active:
        return None
    return grant.user
