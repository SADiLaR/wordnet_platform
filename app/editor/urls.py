from django.urls import path

from . import views

app_name = "editor"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("browse/synsets/", views.browse_synsets, name="browse_synsets"),
    path(
        "browse/synsets/<int:wn_pk>/",
        views.browse_synsets_by_wordnet,
        name="browse_synsets_by_wordnet",
    ),
]
