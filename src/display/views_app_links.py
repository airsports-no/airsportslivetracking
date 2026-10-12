"""
Links that open the mobile app: the "get the app" landing page that the hangar flyer's QR code points to, and the
well-known files that let Android and iOS open those links in the app instead of the browser.
"""

from urllib.parse import quote

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control

GET_APP_PATH = "/get-app/"


def safe_next_path(value):
    """
    The page the link leads to, only ever a path on this site (never another host): '/schedule-flight?contestId=1'
    is fine, '//evil.example' and 'https://evil.example' are not.
    """
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value or "\n" in value or "\r" in value:
        return None
    return value


def get_app_link(request, next_path):
    """The link for a flyer: opens the app (when installed) on [next_path], otherwise offers the app download."""
    base = request.build_absolute_uri("/")[:-1]
    return f"{base}{GET_APP_PATH}?next={quote(next_path, safe='')}"


def get_app_landing(request):
    """
    Shown in the browser when the app does not handle the link (not installed, or the phone is not verified for it):
    install buttons for the pilot's phone, and the plain web page as a way to carry on without the app.
    """
    next_path = safe_next_path(request.GET.get("next"))
    agent = request.META.get("HTTP_USER_AGENT", "").lower()
    platform = "ios" if ("iphone" in agent or "ipad" in agent) else "android" if "android" in agent else "other"
    return render(
        request,
        "display/get_app.html",
        {
            "next_path": next_path,
            "platform": platform,
            "android_url": settings.MOBILE_ANDROID_STORE_URL,
            "ios_url": settings.MOBILE_IOS_STORE_URL,
            # Play passes this to the app after the install (Install Referrer), so the registration continues there.
            "android_install_url": settings.MOBILE_ANDROID_STORE_URL
            + ("&referrer=" + quote("next=" + quote(next_path, safe=""), safe="") if next_path else ""),
        },
    )


@cache_control(public=True, max_age=300)
def assetlinks(request):
    """Android App Links: which app may open links of this site."""
    statements = []
    if settings.MOBILE_ANDROID_CERT_SHA256:
        statements.append(
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": settings.MOBILE_ANDROID_PACKAGE,
                    "sha256_cert_fingerprints": settings.MOBILE_ANDROID_CERT_SHA256,
                },
            }
        )
    return JsonResponse(statements, safe=False)


@cache_control(public=True, max_age=300)
def apple_app_site_association(request):
    """iOS universal links: the app opens the get-app links."""
    details = []
    if settings.MOBILE_IOS_APP_ID:
        details.append({"appIDs": [settings.MOBILE_IOS_APP_ID], "components": [{"/": GET_APP_PATH + "*"}]})
    return JsonResponse({"applinks": {"details": details}})
