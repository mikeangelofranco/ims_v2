import pytest
from django.db import models

from apps.tenancy.context import get_current_tenant, tenant_context
from apps.tenancy.exceptions import TenantContextMissing
from apps.tenancy.models import Tenant


def test_context_fails_closed_without_tenant():
    with pytest.raises(TenantContextMissing):
        get_current_tenant()


def test_context_restores_previous_tenant():
    outer = object()
    inner = object()
    with tenant_context(outer):
        assert get_current_tenant() is outer
        with tenant_context(inner):
            assert get_current_tenant() is inner
        assert get_current_tenant() is outer
    assert get_current_tenant(required=False) is None


@pytest.mark.django_db
def test_tenant_uses_uuid_primary_key():
    tenant = Tenant.objects.create(name="Example", slug="example")
    assert isinstance(Tenant._meta.get_field("id"), models.UUIDField)
    assert tenant.id is not None
