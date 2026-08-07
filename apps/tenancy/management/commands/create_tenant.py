from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.tenancy.models import Tenant, TenantDomain


class Command(BaseCommand):
    help = "Create a tenant and its primary hostname."

    def add_arguments(self, parser):
        parser.add_argument("name")
        parser.add_argument("hostname")
        parser.add_argument("--slug")

    @transaction.atomic
    def handle(self, *args, **options):
        slug = options["slug"] or slugify(options["name"])
        if not slug:
            raise CommandError("The tenant slug cannot be empty.")
        if Tenant.objects.filter(slug=slug).exists():
            raise CommandError(f"Tenant slug '{slug}' already exists.")

        tenant = Tenant.objects.create(name=options["name"], slug=slug)
        TenantDomain.objects.create(
            tenant=tenant,
            hostname=options["hostname"],
            is_primary=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Created tenant '{tenant}' ({tenant.id})."))
