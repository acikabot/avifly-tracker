from django.urls import path

from avifly.docs import views

app_name = "docs"

urlpatterns = [
    path("", views.DocIndexView.as_view(), name="index"),
    path("images/<str:name>", views.image, name="image"),
    path("<slug:slug>/", views.DocPageView.as_view(), name="page"),
]
