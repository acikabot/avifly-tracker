from django.urls import path

from avifly.money import views

app_name = "money"

urlpatterns = [
    path("", views.MoneyBookView.as_view(), name="book"),
    path("costs/", views.CostListView.as_view(), name="costs"),
    path("costs/add/", views.CostCreateView.as_view(), name="cost_add"),
    path("costs/<int:pk>/", views.CostUpdateView.as_view(), name="cost_edit"),
    path("costs/<int:pk>/delete/", views.CostDeleteView.as_view(), name="cost_delete"),
]
