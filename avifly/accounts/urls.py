from django.urls import path

from avifly.accounts import views

app_name = "accounts"

urlpatterns = [
    path("me/", views.ProfileView.as_view(), name="profile"),
    path("users/", views.UserListView.as_view(), name="users"),
    path("users/<int:pk>/approve/", views.ApproveUserView.as_view(), name="approve"),
    path("users/<int:pk>/reject/", views.RejectUserView.as_view(), name="reject"),
    path("users/<int:pk>/access/", views.UserAccessView.as_view(), name="user_access"),
    path("roles/", views.RoleListView.as_view(), name="roles"),
    path("roles/add/", views.RoleEditView.as_view(), name="role_add"),
    path("roles/<int:pk>/", views.RoleEditView.as_view(), name="role_edit"),
    path("roles/<int:pk>/delete/", views.RoleDeleteView.as_view(), name="role_delete"),
]
