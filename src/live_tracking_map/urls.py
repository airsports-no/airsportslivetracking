"""
live_tracking_map URL Configuration
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView, TemplateView
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from display.views import (
    ContestList,
    global_map,
    view_token,
    firebase_token_login,
)
from . import api


class BothHttpAndHttpsSchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, request=None, public=False):
        schema = super().get_schema(request, public)
        schema.schemes = ["http", "https"]
        return schema


docs = get_schema_view(
    openapi.Info(
        title="Airsports tracking API",
        default_version="v1",
        description="Full API for Airsports tracker",
    ),
    generator_class=BothHttpAndHttpsSchemaGenerator,
    permission_classes=(permissions.IsAuthenticated,),
)

urlpatterns = [
    path("contests/", ContestList.as_view(), name="contest_list"),
    path(
        "terms_and_conditions/",
        TemplateView.as_view(template_name="display/terms_and_conditions.html"),
        name="terms_and_conditions",
    ),
    path("admin/", admin.site.urls),
    path("display/", include("display.urls")),
    path("display/api/", include("display.urls_api")),
    path("links/", include("firebase.urls")),
    path("accounts/token/", view_token, name="token"),
    path("accounts/password_change/done/", RedirectView.as_view(url="/", permanent=False)),
    path("accounts/", include("django.contrib.auth.urls")),
    path("firebase_login/", firebase_token_login),
    path("docs/", docs.with_ui()),
    path("api/v1/", include(api.urlpatters)),
    re_path(r"^.?", global_map, name="globalmap"),
]
