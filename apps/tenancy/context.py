from contextlib import contextmanager
from contextvars import ContextVar

from .exceptions import TenantContextMissing

_current_tenant = ContextVar("current_tenant", default=None)


def get_current_tenant(*, required=True):
    tenant = _current_tenant.get()
    if required and tenant is None:
        raise TenantContextMissing("Tenant-owned data requires an active tenant context.")
    return tenant


@contextmanager
def tenant_context(tenant):
    token = _current_tenant.set(tenant)
    try:
        yield tenant
    finally:
        _current_tenant.reset(token)
