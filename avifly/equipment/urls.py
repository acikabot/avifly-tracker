from django.urls import path

from avifly.equipment import views

app_name = "equipment"

urlpatterns = [
    path("", views.EquipmentListView.as_view(), name="list"),
    path("add/", views.EquipmentCreateView.as_view(), name="add"),
    path("<int:pk>/", views.EquipmentDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.EquipmentUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.EquipmentDeleteView.as_view(), name="delete"),
]
