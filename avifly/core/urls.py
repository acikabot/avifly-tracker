from django.urls import path

from avifly.core import views

app_name = "core"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("settings/", views.SettingsView.as_view(), name="settings"),
    path("settings/business/", views.BusinessSettingsView.as_view(), name="business_settings"),
    path("settings/lists/<str:key>/", views.LookupListView.as_view(), name="lookup_list"),
    path("settings/lists/<str:key>/add/", views.LookupEditView.as_view(), name="lookup_add"),
    path("settings/lists/<str:key>/<int:pk>/", views.LookupEditView.as_view(), name="lookup_edit"),
    path(
        "settings/lists/<str:key>/<int:pk>/delete/",
        views.LookupDeleteView.as_view(),
        name="lookup_delete",
    ),
    path("bin/", views.BinView.as_view(), name="bin"),
    path("bin/<str:key>/<int:pk>/restore/", views.RestoreView.as_view(), name="restore"),
    path("bin/<str:key>/<int:pk>/purge/", views.PurgeView.as_view(), name="purge"),
    path("media/<path:path>", views.protected_media, name="media"),
    path("healthz", views.healthz, name="healthz"),
]
