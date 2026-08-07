import pytest
from django.db import connection, models

from apps.tenancy.context import tenant_context
from apps.tenancy.exceptions import TenantBoundaryViolation, TenantContextMissing
from apps.tenancy.models import Tenant, TenantOwnedModel


class ExampleTenantRecord(TenantOwnedModel):
    name = models.CharField(max_length=40)

    class Meta:
        app_label = "tenancy"
        db_table = "test_example_tenant_record"


@pytest.mark.django_db(transaction=True)
def test_default_manager_isolates_records_and_fails_without_context():
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(ExampleTenantRecord)

    try:
        first = Tenant.objects.create(name="First", slug="first")
        second = Tenant.objects.create(name="Second", slug="second")
        with tenant_context(first):
            ExampleTenantRecord.objects.create(name="First record")
        with tenant_context(second):
            ExampleTenantRecord.objects.create(name="Second record")

        with tenant_context(first):
            assert list(ExampleTenantRecord.objects.values_list("name", flat=True)) == [
                "First record"
            ]
        with tenant_context(second):
            assert list(ExampleTenantRecord.objects.values_list("name", flat=True)) == [
                "Second record"
            ]
        with pytest.raises(TenantContextMissing):
            ExampleTenantRecord.objects.count()
        assert ExampleTenantRecord.all_objects.count() == 2

        with tenant_context(first):
            with pytest.raises(TenantBoundaryViolation):
                ExampleTenantRecord.objects.create(tenant=second, name="Unsafe")
            with pytest.raises(TenantBoundaryViolation):
                ExampleTenantRecord.objects.update(tenant=second)
    finally:
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(ExampleTenantRecord)
