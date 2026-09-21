"""Make an existing account an owner (used to set up the first owner).

python manage.py makeowner <username-or-email>
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from avifly.accounts.models import User


class Command(BaseCommand):
    help = "Approve an account and give it full owner access."

    def add_arguments(self, parser):
        parser.add_argument("login", help="Username or e-mail address of an existing account")

    def handle(self, *args, login: str, **options):
        user = User.objects.filter(Q(username__iexact=login) | Q(email__iexact=login)).first()
        if user is None:
            raise CommandError(f"No account called '{login}'. Sign up in the app first.")
        user.is_active = True
        user.is_superuser = True
        user.is_staff = True
        user.approved_at = user.approved_at or timezone.now()
        user.save()
        user.groups.clear()
        self.stdout.write(self.style.SUCCESS(f"{user.username} is now an owner."))
