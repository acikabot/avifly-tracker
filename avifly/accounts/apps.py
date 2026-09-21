from django.utils.translation import gettext_lazy as _

from avifly.core.modules import AviflyModule
from avifly.core.registry import MenuItem, PermissionSection, Registry


def pending_signups(user) -> int | None:
    if not user.has_perm("accounts.manage_users"):
        return None
    from avifly.accounts.models import User

    return User.objects.pending().count()


class AccountsConfig(AviflyModule):
    default = True  # this module's config (apps.py also imports the AviflyModule base)
    name = "avifly.accounts"
    label = "accounts"
    verbose_name = _("Users")
    requires = ("core",)
    url_prefix = "people/"

    def register(self, registry: Registry) -> None:
        from auditlog.registry import auditlog

        from avifly.accounts.models import User

        auditlog.register(
            User,
            include_fields=[
                "username", "email", "first_name", "last_name",
                "is_active", "is_superuser", "approved_at",
            ],
            m2m_fields={"groups"},
        )  # fmt: skip

        registry.add_menu_item(
            MenuItem(
                key="users",
                label=_("Users"),
                url_name="accounts:users",
                icon="people",
                permission="accounts.manage_users",
                area="settings",
                order=20,
                badge=pending_signups,
                namespace="accounts",
            )
        )
        registry.add_menu_item(
            MenuItem(
                key="roles",
                label=_("Roles & permissions"),
                url_name="accounts:roles",
                icon="shield-lock",
                permission="accounts.manage_users",
                area="settings",
                order=21,
                namespace="accounts",
            )
        )
        registry.add_permission_section(
            PermissionSection(
                key="users",
                label=_("Users"),
                model="accounts.user",
                actions=(),
                extra_permissions=(
                    ("accounts.manage_users", _("Approve sign-ups and manage roles")),
                ),
                order=800,
            )
        )
