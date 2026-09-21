from django.urls import path

from avifly.customers import views

app_name = "customers"

urlpatterns = [
    path("", views.CustomerListView.as_view(), name="list"),
    path("add/", views.CustomerCreateView.as_view(), name="add"),
    path("search.json", views.CustomerSearchView.as_view(), name="search"),
    path("quick-add/", views.QuickAddCustomerView.as_view(), name="quick_add"),
    path("<int:pk>/", views.CustomerDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.CustomerUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.CustomerDeleteView.as_view(), name="delete"),
    path("<int:pk>/job-data.json", views.CustomerJobDataView.as_view(), name="job_data"),
    path("<int:pk>/fields/quick-add/", views.QuickAddFieldView.as_view(), name="field_quick_add"),
    path("<int:customer_pk>/fields/add/", views.FarmFieldCreateView.as_view(), name="field_add"),
    path("fields/<int:pk>/edit/", views.FarmFieldUpdateView.as_view(), name="field_edit"),
    path("fields/<int:pk>/delete/", views.FarmFieldDeleteView.as_view(), name="field_delete"),
]
