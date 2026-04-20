"""
live_tracking_map URL Configuration
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.views.decorators.cache import cache_page
from django.views.generic import RedirectView, TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework import permissions
from django_js_reverse.views import urls_json

from display.views import (
    FrontEndView,
    view_token,
    firebase_token_login,
)
from . import api

urlpatterns = [
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
    path("firebase_login/", firebase_token_login),  # Required, used by app
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/v1/reverse-urls/", cache_page(3600)(urls_json), name="js_reverse"),
    path("api/v1/", include(api.urlpatterns)),
    path(
        "global/contest_details/<int:pk>/",
        RedirectView.as_view(url="/mission-dashboard/%(pk)s/", permanent=True, query_string=True),
    ),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns += [
    re_path(r"^.?", FrontEndView.as_view(), name="frontend"),
]
