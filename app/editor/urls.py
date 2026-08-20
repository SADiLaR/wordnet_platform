from django.urls import path

from . import views

app_name = "editor"

urlpatterns = [
    path("queue/", views.assignment_queue, name="assignment_queue"),
    path(
        "queue/<int:wn_pk>/", views.assignment_queue, name="assignment_queue_by_wordnet"
    ),
    path("synsets/", views.browse_synsets, name="browse_synsets"),
    path(
        "synsets/<int:wn_pk>/",
        views.browse_synsets,
        name="browse_synsets_by_wordnet",
    ),
]
