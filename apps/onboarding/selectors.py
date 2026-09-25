from apps.businesses.models import BusinessProfile
from apps.tenancy.context import tenant_context
from apps.tenancy.models import TenantMembership, TenantRole, TenantStatus


def get_owned_workspace(user):
    if not user.is_authenticated:
        return None
    membership = (
        TenantMembership.objects.select_related("tenant")
        .filter(
            user=user,
            role=TenantRole.OWNER,
            is_active=True,
            tenant__status=TenantStatus.ACTIVE,
        )
        .order_by("created_at")
        .first()
    )
    return membership.tenant if membership else None


def get_business_profile(tenant):
    if tenant is None:
        return None
    with tenant_context(tenant):
        return BusinessProfile.objects.first()


def get_onboarding_stage(user):
    if not user.is_authenticated:
        return "account"
    tenant = get_owned_workspace(user)
    if tenant is None:
        return "workspace"
    if get_business_profile(tenant) is None:
        return "business"
    return "ready"
