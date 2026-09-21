"""Account rules: approving sign-ups and changing who is an owner."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from avifly.accounts.models import User


def owners_count(exclude: User | None = None) -> int:
    qs = User.objects.owners()
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    return qs.count()


@transaction.atomic
def approve_user(user: User, *, by: User, role: Group | None, make_owner: bool = False) -> User:
    if make_owner and not by.is_superuser:
        raise ValidationError(_("Only owners can make someone an owner."))
    user.is_active = True
    user.approved_at = timezone.now()
    user.approved_by = by
    user.is_superuser = make_owner
    user.is_staff = make_owner
    user.save()
    user.groups.set([role] if role and not make_owner else [])
    notify_user_approved(user)
    return user


@transaction.atomic
def update_access(
    user: User, *, by: User, role: Group | None, make_owner: bool, active: bool
) -> User:
    """Change someone's role/owner status, protecting the last remaining owner."""
    changing_owner = make_owner != user.is_superuser
    if changing_owner and not by.is_superuser:
        raise ValidationError(_("Only owners can add or remove owners."))
    losing_owner = user.is_owner and (not make_owner or not active)
    if losing_owner and owners_count(exclude=user) == 0:
        raise ValidationError(_("There must always be at least one active owner."))
    user.is_superuser = make_owner
    user.is_staff = make_owner
    user.is_active = active
    if active and user.approved_at is None:
        user.approved_at = timezone.now()
        user.approved_by = by
    user.save()
    user.groups.set([role] if role and not make_owner else [])
    return user


def reject_signup(user: User) -> None:
    if not user.is_pending:
        raise ValidationError(_("Only pending sign-ups can be rejected."))
    user.delete()


def _absolute(request, url: str) -> str:
    return request.build_absolute_uri(url) if request is not None else url


def notify_owners_of_signup(user: User, request=None) -> None:
    recipients = [o.email for o in User.objects.owners() if o.email]
    if not recipients:
        return
    link = _absolute(request, reverse("accounts:users"))
    send_mail(
        subject=_("New sign-up waiting for approval: %(name)s") % {"name": user.username},
        message=_(
            "%(name)s (%(email)s) signed up and is waiting for approval.\n\n"
            "Approve or reject them here: %(link)s"
        )
        % {"name": user.display_name, "email": user.email, "link": link},
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=True,
    )


def notify_user_approved(user: User) -> None:
    if not user.email:
        return
    send_mail(
        subject=_("Your account has been approved"),
        message=_("Hi %(name)s,\n\nAn owner approved your account — you can sign in now.")
        % {"name": user.display_name},
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
