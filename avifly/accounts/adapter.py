from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings

from avifly.accounts.services import notify_owners_of_signup


class AccountAdapter(DefaultAccountAdapter):
    """Open sign-up, but new accounts stay inactive until an owner approves them."""

    def is_open_for_signup(self, request) -> bool:
        return settings.AVIFLY_SIGNUP_OPEN

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        user.is_active = False
        if commit:
            user.save()
            notify_owners_of_signup(user, request)
        return user
