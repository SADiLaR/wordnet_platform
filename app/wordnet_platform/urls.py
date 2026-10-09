"""
URL configuration for wordnet_platform project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from lex.concerns import concerns_detail, concerns_report

from . import views
from .forms import AuthenticationForm

urlpatterns = [
    path(
        "admin/concerns/",
        admin.site.admin_view(concerns_report),
        name="concerns_report",
    ),
    path(
        "admin/concerns/<str:model_name>/<str:concern_key>/",
        admin.site.admin_view(concerns_detail),
        name="concerns_detail",
    ),
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(authentication_form=AuthenticationForm),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("editor.urls")),
    path("_health/", views.health, name="health"),
]
if settings.DEBUG and settings.DEBUG_TOOLBAR:
    urlpatterns.append(path("__debug__/", include("debug_toolbar.urls")))
