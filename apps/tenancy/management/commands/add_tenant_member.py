from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.tenancy.models import TenantDomain, TenantMembership, TenantRole


class Command(BaseCommand):
    help = "Add or reactivate a user's membership for a tenant hostname."

    def add_arguments(self, parser):
        parser.add_argument("hostname")
        parser.add_argument("email")
        parser.add_argument("role", choices=TenantRole.values)

    def handle(self, *args, **options):
        try:
            domain = TenantDomain.objects.select_related("tenant").get(
                hostname=options["hostname"].strip().rstrip(".").lower(),
                is_active=True,
            )
        except TenantDomain.DoesNotExist as exc:
            raise CommandError("No active tenant domain matches that hostname.") from exc

        user_model = get_user_model()
        try:
            user = user_model.objects.get(email__iexact=options["email"])
        except user_model.DoesNotExist as exc:
            raise CommandError("No user matches that email address.") from exc

        membership, created = TenantMembership.objects.update_or_create(
            tenant=domain.tenant,
            user=user,
            defaults={"role": options["role"], "is_active": True},
        )
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} membership {membership.id}."))
