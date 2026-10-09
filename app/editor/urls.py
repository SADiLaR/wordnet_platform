from django.urls import path

from . import views

app_name = "editor"

urlpatterns = [
    path("", views.front_page, name="front_page"),
    path("about/", views.about, name="about"),
    path("queue/", views.assignment_queue, name="assignment_queue"),
    path(
        "queue/<int:wn_pk>/", views.assignment_queue, name="assignment_queue_by_wordnet"
    ),
    path("synsets/", views.browse_synsets, name="browse_synsets"),
    path(
        "synsets/<int:pk>/",
        views.synset_detail,
        name="synset_detail",
    ),
    path(
        "synsets/<int:pk>/status/",
        views.synset_status_htmx,
        name="synset_status_htmx",
    ),
    path(
        "synsets/<int:pk>/definition/",
        views.synset_definition,
        name="synset_definition",
    ),
    path(
        "synsets/<int:pk>/relations/add/",
        views.add_relation_htmx,
        name="add_relation_htmx",
    ),
    path(
        "synsets/<int:pk>/relations/form/",
        views.add_relation_form_htmx,
        name="add_relation_form_htmx",
    ),
    path(
        "synsets/<int:pk>/relations/search/",
        views.search_synsets_htmx,
        name="search_synsets_htmx",
    ),
    path(
        "synsets/<int:synset_pk>/relations/delete/<int:rel_pk>/",
        views.delete_relation_htmx,
        name="delete_relation_htmx",
    ),
    path(
        "clear/",
        views.clear_htmx,
        name="clear_htmx",
    ),
]
