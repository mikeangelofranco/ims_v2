from django.conf import settings
from django.db import transaction

from apps.accounts.models import User
from apps.businesses.models import BusinessProfile
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Tenant, TenantDomain, TenantMembership, TenantRole


@transaction.atomic
def create_account(*, first_name, email, password):
    return User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name.strip(),
    )


@transaction.atomic
def update_account(*, user, first_name, email, password):
    user.first_name = first_name.strip()
    user.email = email
    update_fields = ["first_name", "email"]
    if password:
        user.set_password(password)
        update_fields.append("password")
    user.save(update_fields=update_fields)
    return user


@transaction.atomic
def create_workspace(*, user, workspace_name, workspace_slug, logo, timezone):
    tenant = Tenant.objects.create(
        name=workspace_name.strip(),
        slug=workspace_slug,
        logo=logo,
        timezone=timezone,
    )
    TenantDomain.objects.create(
        tenant=tenant,
        hostname=f"{workspace_slug}.{settings.TENANT_BASE_DOMAIN}",
        is_primary=True,
    )
    TenantMembership.objects.create(
        tenant=tenant,
        user=user,
        role=TenantRole.OWNER,
    )
    return tenant


@transaction.atomic
def update_workspace(*, tenant, workspace_name, workspace_slug, logo, timezone):
    tenant.name = workspace_name.strip()
    tenant.slug = workspace_slug
    tenant.timezone = timezone
    update_fields = ["name", "slug", "timezone", "updated_at"]
    if logo:
        tenant.logo = logo
        update_fields.append("logo")
    tenant.save(update_fields=update_fields)
    primary_domain = tenant.domains.select_for_update().get(is_primary=True)
    primary_domain.hostname = f"{workspace_slug}.{settings.TENANT_BASE_DOMAIN}"
    primary_domain.save(update_fields=["hostname", "updated_at"])
    return tenant


@transaction.atomic
def create_business_profile(
    *,
    tenant,
    legal_name,
    industry,
    company_size,
    currency,
    timezone,
    business_email,
    address,
    tax_identifier,
    registration_number,
):
    tenant.timezone = timezone
    tenant.save(update_fields=["timezone", "updated_at"])
    with tenant_context(tenant):
        return BusinessProfile.objects.create(
            legal_name=legal_name.strip(),
            industry=industry,
            company_size=company_size,
            currency=currency,
            business_email=business_email,
            address=address.strip(),
            tax_identifier=tax_identifier.strip(),
            registration_number=registration_number.strip(),
        )
