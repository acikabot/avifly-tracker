from __future__ import annotations

from allauth.account.adapter import get_adapter
from allauth.account.forms import SignupForm as AllauthSignupForm
from allauth.core import context as allauth_context
from django import forms
from django.contrib.auth.models import Group, Permission
from django.utils.translation import gettext_lazy as _

from avifly.accounts import turnstile
from avifly.accounts.models import User
from avifly.core.registry import PermissionSection, registry

ACTION_LABELS = {
    "view": _("See"),
    "add": _("Add"),
    "change": _("Edit"),
    "delete": _("Delete"),
}

SCOPE_CHOICES = [("own", _("Only their own")), ("all", _("Everyone's"))]


class SignupForm(AllauthSignupForm):
    """Sign-up with an optional name and, when configured, a Cloudflare bot check."""

    first_name = forms.CharField(label=_("First name"), max_length=150, required=False)
    last_name = forms.CharField(label=_("Last name"), max_length=150, required=False)

    field_order = ["first_name", "last_name", "email", "username", "password1", "password2"]

    def clean(self):
        cleaned = super().clean()
        if turnstile.is_enabled():
            request = allauth_context.request
            token = self.data.get("cf-turnstile-response", "")
            remote_ip = get_adapter().get_client_ip(request) if request else None
            if not turnstile.verify(token, remote_ip):
                raise forms.ValidationError(_("The bot check failed. Please try again."))
        return cleaned


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name"]


def role_choices():
    return Group.objects.order_by("name")


class ApproveForm(forms.Form):
    role = forms.ModelChoiceField(
        queryset=Group.objects.none(), required=False, empty_label=_("No role (sees nothing)")
    )
    make_owner = forms.BooleanField(label=_("Make owner (full access)"), required=False)

    def __init__(self, *args, can_make_owner: bool, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = role_choices()
        if not can_make_owner:
            del self.fields["make_owner"]


class UserAccessForm(forms.Form):
    role = forms.ModelChoiceField(
        label=_("Role"),
        queryset=Group.objects.none(),
        required=False,
        empty_label=_("No role (sees nothing)"),
    )
    make_owner = forms.BooleanField(
        label=_("Owner"),
        required=False,
        help_text=_("Owners can do everything, including managing users and roles."),
    )
    active = forms.BooleanField(
        label=_("Active"), required=False, help_text=_("Inactive people can't sign in.")
    )

    def __init__(self, *args, user: User, can_make_owner: bool, **kwargs):
        kwargs.setdefault(
            "initial",
            {"role": user.role, "make_owner": user.is_superuser, "active": user.is_active},
        )
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = role_choices()
        if not can_make_owner:
            self.fields["make_owner"].disabled = True


# -- role editor -------------------------------------------------------------------------
def _perm_key(perm: str) -> str:
    return perm.replace(".", "__")


def _action_perm(section: PermissionSection, action: str) -> str:
    app_label, model = section.model.split(".")
    return f"{app_label}.{action}_{model}"


def _permission_objects(names: set[str]) -> list[Permission]:
    perms = []
    for name in names:
        app_label, codename = name.split(".", 1)
        perm = Permission.objects.filter(
            content_type__app_label=app_label, codename=codename
        ).first()
        if perm is not None:
            perms.append(perm)
    return perms


class RoleRow:
    """One module's checkboxes in the role editor."""

    def __init__(self, section, actions, scope, extras):
        self.section = section
        self.actions = actions
        self.scope = scope
        self.extras = extras


class RoleForm(forms.ModelForm):
    """Name a role and tick what it may do in each module (built from the registry)."""

    class Meta:
        model = Group
        fields = ["name"]
        labels = {"name": _("Role name")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sections = registry.permission_sections()
        current = set()
        if self.instance.pk:
            current = {
                f"{p.content_type.app_label}.{p.codename}"
                for p in self.instance.permissions.select_related("content_type")
            }
        for section in self.sections:
            for action in section.actions:
                self.fields[f"{section.key}__{action}"] = forms.BooleanField(
                    label=ACTION_LABELS.get(action, action),
                    required=False,
                    initial=_action_perm(section, action) in current,
                )
            if section.scope_permissions:
                has_all = all(p in current for p in section.scope_permissions)
                self.fields[f"{section.key}__scope"] = forms.ChoiceField(
                    label=_("Whose records"),
                    choices=SCOPE_CHOICES,
                    required=False,
                    initial="all" if has_all else "own",
                )
            for perm, label in section.extra_permissions:
                self.fields[f"extra__{_perm_key(perm)}"] = forms.BooleanField(
                    label=label, required=False, initial=perm in current
                )

    def rows(self) -> list[RoleRow]:
        rows = []
        for section in self.sections:
            actions = [self[f"{section.key}__{a}"] for a in section.actions]
            scope = self[f"{section.key}__scope"] if section.scope_permissions else None
            extras = [self[f"extra__{_perm_key(p)}"] for p, _label in section.extra_permissions]
            rows.append(RoleRow(section, actions, scope, extras))
        return rows

    def selected_permissions(self) -> set[str]:
        data = self.cleaned_data
        selected: set[str] = set()
        for section in self.sections:
            ticked = [a for a in section.actions if data.get(f"{section.key}__{a}")]
            # Adding, editing or deleting something implies being able to see it.
            if ticked and "view" in section.actions and "view" not in ticked:
                ticked.append("view")
            selected.update(_action_perm(section, a) for a in ticked)
            if ticked and section.scope_permissions and data.get(f"{section.key}__scope") == "all":
                selected.update(section.scope_permissions)
            for perm, _label in section.extra_permissions:
                if data.get(f"extra__{_perm_key(perm)}"):
                    selected.add(perm)
        return selected

    def save(self, commit=True):
        group = super().save(commit=True)
        group.permissions.set(_permission_objects(self.selected_permissions()))
        return group
