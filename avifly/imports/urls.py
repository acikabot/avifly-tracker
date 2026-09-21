from django.urls import path

from avifly.imports import views

app_name = "imports"

urlpatterns = [
    path("", views.ImportIndexView.as_view(), name="index"),
    path("<int:pk>/", views.BatchView.as_view(), name="batch"),
]
