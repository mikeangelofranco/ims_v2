import pytest
from django.contrib.auth import get_user_model

from apps.inventory.models import Category, Location, Product, StockLevel
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Tenant, TenantDomain, TenantMembership, TenantRole


@pytest.fixture
def workspace():
    tenant = Tenant.objects.create(name="Acme", slug="acme")
    other = Tenant.objects.create(name="Other", slug="other")
    TenantDomain.objects.create(tenant=tenant, hostname="acme.localhost")
    user = get_user_model().objects.create_user(email="owner@example.com", password="pass")
    member = TenantMembership.objects.create(tenant=tenant, user=user, role=TenantRole.OWNER)
    with tenant_context(other):
        foreign = Product.objects.create(name="Foreign secret", sku="FOREIGN")
        foreign_category = Category.objects.create(name="Foreign", slug="foreign")
    with tenant_context(tenant):
        category = Category.objects.create(name="Audio", slug="audio")
        location = Location.objects.create(name="Main", code="main")
        for name, quantity, minimum, active in (
            ("Healthy", 20, 5, True),
            ("Low", 5, 5, True),
            ("Empty", 0, 5, True),
            ("Inactive", 10, 5, False),
        ):
            product = Product.objects.create(
                name=name, sku=name, barcode=name + "-BAR", category=category, is_active=active
            )
            StockLevel.objects.create(
                product=product, location=location, quantity=quantity, minimum_quantity=minimum
            )
    return tenant, user, member, foreign, foreign_category, location
