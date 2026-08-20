from django.urls import path

from . import views

app_name = "editor"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("browse/synsets/", views.browse_synsets, name="browse_synsets"),
]
