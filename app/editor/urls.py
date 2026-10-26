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
        "synsets/<int:pk>/delete/",
        views.delete_synset,
        name="delete_synset",
    ),
    path(
        "synsets/<int:pk>/status/",
        views.synset_status_htmx,
        name="synset_status_htmx",
    ),
    path(
        "synsets/<int:pk>/link_source/form/",
        views.link_synset_form_htmx,
        name="link_synset_form_htmx",
    ),
    path(
        "synsets/<int:pk>/link_source/",
        views.link_synset_htmx,
        name="link_synset_htmx",
    ),
    path(
        "synsets/<int:pk>/definition/",
        views.synset_definition,
        name="synset_definition",
    ),
    path(
        "synsets/<int:pk>/senses/add/",
        views.add_sense_htmx,
        name="add_sense_htmx",
    ),
    path(
        "synsets/<int:pk>/senses/search/",
        views.search_words_htmx,
        name="search_words_htmx",
    ),
    path(
        "synset/<int:synset_pk>/example/delete/<int:pk>/",
        views.delete_synset_example_htmx,
        name="delete_synset_example_htmx",
    ),
    path(
        "synsets/<int:synset_pk>/senses/delete/<int:sense_pk>/",
        views.delete_sense_htmx,
        name="delete_sense_htmx",
    ),
    path(
        "synsets/<int:synset_pk>/sense_examples/add/",
        views.save_sense_example_htmx,
        name="add_sense_example_htmx",
    ),
    path(
        "synsets/<int:synset_pk>/sense_examples/<int:example_pk>/edit/",
        views.save_sense_example_htmx,
        name="edit_sense_example_htmx",
    ),
    path(
        "synsets/<int:synset_pk>/sense_examples/<int:example_pk>/delete/",
        views.delete_sense_example_htmx,
        name="delete_sense_example_htmx",
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
        "synsets/<int:pk>/search/",
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
