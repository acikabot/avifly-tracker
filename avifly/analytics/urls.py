from django.urls import path

from avifly.analytics import views

app_name = "analytics"

urlpatterns = [
    path("", views.AnalyticsView.as_view(), name="index"),
]
