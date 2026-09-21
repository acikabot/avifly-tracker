from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from avifly.accounts import services
from avifly.accounts.forms import ApproveForm, ProfileForm, RoleForm, UserAccessForm
from avifly.accounts.models import User
from avifly.core.mixins import PermissionRequired


class ProfileView(TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        kwargs.setdefault("form", ProfileForm(instance=self.request.user))
        return super().get_context_data(**kwargs)

    def post(self, request):
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Your details were saved."))
            return redirect("accounts:profile")
        return self.render_to_response(self.get_context_data(form=form))


class ManageUsersMixin(PermissionRequired):
    permission_required = "accounts.manage_users"


class UserListView(ManageUsersMixin, TemplateView):
    template_name = "accounts/user_list.html"

    def get_context_data(self, **kwargs):
        can_make_owner = self.request.user.is_superuser
        pending = [
            (u, ApproveForm(prefix=f"u{u.pk}", can_make_owner=can_make_owner))
            for u in User.objects.pending().order_by("date_joined")
        ]
        active = User.objects.filter(is_active=True).prefetch_related("groups")
        inactive = User.objects.filter(is_active=False).exclude(
            pk__in=[u.pk for u, _form in pending]
        )
        return super().get_context_data(pending=pending, active=active, inactive=inactive, **kwargs)


class ApproveUserView(ManageUsersMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User.objects.pending(), pk=pk)
        form = ApproveForm(
            request.POST, prefix=f"u{user.pk}", can_make_owner=request.user.is_superuser
        )
        if form.is_valid():
            try:
                services.approve_user(
                    user,
                    by=request.user,
                    role=form.cleaned_data["role"],
                    make_owner=form.cleaned_data.get("make_owner", False),
                )
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
            else:
                messages.success(
                    request, _("%(name)s can sign in now.") % {"name": user.display_name}
                )
        return redirect("accounts:users")


class RejectUserView(ManageUsersMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User.objects.pending(), pk=pk)
        name = user.username
        services.reject_signup(user)
        messages.success(request, _("Sign-up from %(name)s rejected.") % {"name": name})
        return redirect("accounts:users")


class UserAccessView(ManageUsersMixin, TemplateView):
    template_name = "accounts/user_access.html"

    def get_user(self) -> User:
        return get_object_or_404(User, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        person = self.get_user()
        kwargs.setdefault(
            "form", UserAccessForm(user=person, can_make_owner=self.request.user.is_superuser)
        )
        return super().get_context_data(person=person, **kwargs)

    def post(self, request, pk):
        person = self.get_user()
        form = UserAccessForm(request.POST, user=person, can_make_owner=request.user.is_superuser)
        if form.is_valid():
            data = form.cleaned_data
            try:
                services.update_access(
                    person,
                    by=request.user,
                    role=data["role"],
                    make_owner=data["make_owner"],
                    active=data["active"],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, _("Access updated."))
                return redirect("accounts:users")
        return self.render_to_response(self.get_context_data(form=form))


class RoleListView(ManageUsersMixin, TemplateView):
    template_name = "accounts/role_list.html"

    def get_context_data(self, **kwargs):
        roles = Group.objects.annotate(people=Count("user")).order_by("name")
        return super().get_context_data(roles=roles, **kwargs)


class RoleEditView(ManageUsersMixin, TemplateView):
    template_name = "accounts/role_form.html"

    def get_role(self):
        pk = self.kwargs.get("pk")
        return get_object_or_404(Group, pk=pk) if pk else None

    def get_context_data(self, **kwargs):
        kwargs.setdefault("form", RoleForm(instance=self.get_role()))
        return super().get_context_data(**kwargs)

    def post(self, request, pk=None):
        form = RoleForm(request.POST, instance=self.get_role())
        if form.is_valid():
            role = form.save()
            messages.success(request, _("Role “%(name)s” saved.") % {"name": role.name})
            return redirect("accounts:roles")
        return self.render_to_response(self.get_context_data(form=form))


class RoleDeleteView(ManageUsersMixin, View):
    def post(self, request, pk):
        role = get_object_or_404(Group, pk=pk)
        if role.user_set.exists():
            messages.error(request, _("Move everyone off this role before deleting it."))
            return redirect("accounts:role_edit", pk=pk)
        role.delete()
        messages.success(request, _("Role deleted."))
        return redirect("accounts:roles")
