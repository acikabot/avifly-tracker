"""URL routing.

Each enabled Avifly module is mounted at its own prefix (``AviflyModule.url_prefix``),
so switching a module off also removes its pages.
"""

from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from avifly.core.registry import registry

urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("", include("avifly.core.urls")),
]

for module in registry.enabled_modules():
    if module.url_prefix is not None and module.name != "avifly.core":
        urlpatterns.append(path(module.url_prefix, include(f"{module.name}.urls")))

if settings.AVIFLY_ADMIN_ENABLED:
    admin.site.site_header = "Avifly admin"
    # Sign-in goes through the app's own login page, so the admin gets the same lockout
    # after failed attempts and the same two-step check. Django's admin login has neither.
    admin.site.login = secure_admin_login(admin.site.login)
    urlpatterns.append(path("admin/", admin.site.urls))
