from django.urls import path

from avifly.jobs import views

app_name = "jobs"

urlpatterns = [
    path("", views.JobListView.as_view(), name="list"),
    path("new/", views.JobEditView.as_view(), name="add"),
    path("<int:pk>/", views.JobDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.JobEditView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.JobDeleteView.as_view(), name="delete"),
    path("<int:pk>/repeat/", views.DuplicateJobView.as_view(), name="duplicate"),
    path("<int:pk>/next-day/", views.NextDayView.as_view(), name="next_day"),
    path("<int:pk>/days/<int:day_pk>/start/", views.StartDayView.as_view(), name="start_day"),
    path("<int:pk>/days/<int:day_pk>/finish/", views.FinishDayView.as_view(), name="finish_day"),
    path("<int:pk>/photos/", views.PhotoUploadView.as_view(), name="photo_upload"),
    path(
        "<int:pk>/photos/<int:photo_pk>/delete/",
        views.PhotoDeleteView.as_view(),
        name="photo_delete",
    ),
]
