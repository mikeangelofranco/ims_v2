from django.db import models

from .context import get_current_tenant
from .exceptions import TenantBoundaryViolation


def _guard_tenant_value(values, tenant):
    supplied_tenant = values.get("tenant")
    supplied_tenant_id = values.get("tenant_id")
    supplied_id = supplied_tenant_id or getattr(supplied_tenant, "pk", None)
    if supplied_id is not None and supplied_id != tenant.pk:
        raise TenantBoundaryViolation("Cannot write data for a different tenant.")
    values.pop("tenant_id", None)
    values["tenant"] = tenant
    return values


class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def create(self, **kwargs):
        tenant = get_current_tenant()
        return super().create(**_guard_tenant_value(kwargs, tenant))

    def bulk_create(self, objs, **kwargs):
        tenant = get_current_tenant()
        for obj in objs:
            if obj.tenant_id is not None and obj.tenant_id != tenant.pk:
                raise TenantBoundaryViolation("Cannot write data for a different tenant.")
            obj.tenant = tenant
        return super().bulk_create(objs, **kwargs)

    def update(self, **kwargs):
        if "tenant" in kwargs or "tenant_id" in kwargs:
            raise TenantBoundaryViolation("A tenant key cannot be changed in bulk.")
        get_current_tenant()
        return super().update(**kwargs)

    def update_or_create(self, defaults=None, create_defaults=None, **kwargs):
        protected_values = (defaults or {}) | (create_defaults or {})
        if "tenant" in protected_values or "tenant_id" in protected_values:
            raise TenantBoundaryViolation("A tenant key cannot be changed by update_or_create.")
        return super().update_or_create(
            defaults=defaults,
            create_defaults=create_defaults,
            **kwargs,
        )

    def bulk_update(self, objs, fields, **kwargs):
        if "tenant" in fields or "tenant_id" in fields:
            raise TenantBoundaryViolation("A tenant key cannot be changed in bulk.")
        tenant = get_current_tenant()
        if any(obj.tenant_id != tenant.pk for obj in objs):
            raise TenantBoundaryViolation("Cannot write data for a different tenant.")
        return super().bulk_update(objs, fields, **kwargs)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    def get_queryset(self):
        tenant = get_current_tenant()
        return super().get_queryset().for_tenant(tenant)
