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
    CombinedFrontEndView,
    view_token,
    firebase_token_login,
    mobile_config,
    firebase_password_change,
    firebase_password_reset,
    signup,
    page_not_found,
)
from display.views_social_login import (
    SocialLoginAwareLoginView,
    desktop_sign_in,
    desktop_sign_in_complete,
    desktop_sign_in_done,
    desktop_sign_in_token,
    firebase_web_login,
)
from display.views_app_links import apple_app_site_association, assetlinks, get_app_landing
from . import api

handler404 = page_not_found

urlpatterns = [
    path("admin/", admin.site.urls),
    path("display/", include("display.urls")),
    path("display/api/", include("display.urls_api")),
    path("links/", include("firebase.urls")),
    path("accounts/token/", view_token, name="token"),
    path("accounts/signup/", signup, name="signup"),
    path("accounts/login/", SocialLoginAwareLoginView.as_view(), name="login"),
    path("accounts/firebase_login/", firebase_web_login, name="firebase_web_login"),
    # Sign-in for the MSFS client with Google or Apple (see display.views_social_login)
    path("accounts/desktop_sign_in/", desktop_sign_in, name="desktop_sign_in"),
    path("accounts/desktop_sign_in/complete/", desktop_sign_in_complete, name="desktop_sign_in_complete"),
    path("accounts/desktop_sign_in/token/", desktop_sign_in_token, name="desktop_sign_in_token"),
    path("accounts/desktop_sign_in/done/", desktop_sign_in_done, name="desktop_sign_in_done"),
    path("accounts/password_change/", firebase_password_change, name="password_change"),
    path("accounts/password_change/done/", RedirectView.as_view(url="/", permanent=False)),
    path("accounts/password_reset/", firebase_password_reset, name="password_reset"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("firebase_login/", firebase_token_login),  # Required, used by app
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/v1/reverse-urls/", urls_json, name="js_reverse"),
    path("api/v1/mobile/config/", mobile_config, name="mobile_config"),
    path("get-app/", get_app_landing, name="get_app"),
    path(".well-known/assetlinks.json", assetlinks, name="assetlinks"),
    path(".well-known/apple-app-site-association", apple_app_site_association, name="apple_app_site_association"),
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
    re_path(r"^(?!api/)(?P<path>.*)", CombinedFrontEndView.as_view(), name="frontend"),
]
