from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel

from .context import get_current_tenant
from .exceptions import TenantBoundaryViolation
from .managers import TenantManager

hostname_validator = RegexValidator(
    regex=r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    message="Enter a lowercase hostname without a scheme, port, or path.",
)


class TenantStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"


class Tenant(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=80, unique=True)
    status = models.CharField(max_length=16, choices=TenantStatus, default=TenantStatus.ACTIVE)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class TenantDomain(UUIDModel, TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="domains")
    hostname = models.CharField(max_length=253, unique=True, validators=[hostname_validator])
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("hostname",)
        constraints = [
            models.UniqueConstraint(
                fields=("tenant",),
                condition=models.Q(is_primary=True),
                name="one_primary_domain_per_tenant",
            )
        ]

    def save(self, *args, **kwargs):
        self.hostname = self.hostname.strip().rstrip(".").lower()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.hostname


class TenantRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Administrator"
    MEMBER = "member", "Member"
    VIEWER = "viewer", "Viewer"


class TenantMembership(UUIDModel, TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tenant_memberships",
    )
    role = models.CharField(max_length=16, choices=TenantRole, default=TenantRole.MEMBER)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("tenant", "user")
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "user"),
                name="unique_user_membership_per_tenant",
            )
        ]
        indexes = [models.Index(fields=("user", "tenant", "is_active"))]

    def __str__(self):
        return f"{self.user} in {self.tenant} ({self.role})"


class TenantOwnedModel(UUIDModel, TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
        default_manager_name = "objects"
        base_manager_name = "all_objects"

    def save(self, *args, **kwargs):
        tenant = get_current_tenant()
        if self.tenant_id is not None and self.tenant_id != tenant.pk:
            raise TenantBoundaryViolation("Cannot save data for a different tenant.")
        self.tenant = tenant
        return super().save(*args, **kwargs)
