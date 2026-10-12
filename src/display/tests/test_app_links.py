from django.test import RequestFactory, TestCase, override_settings

from display.views_app_links import get_app_link, safe_next_path


class TestSafeNextPath(TestCase):
    def test_only_paths_on_this_site_are_accepted(self):
        self.assertEqual(safe_next_path("/schedule-flight?contestId=1"), "/schedule-flight?contestId=1")
        self.assertIsNone(safe_next_path(None))
        self.assertIsNone(safe_next_path(""))
        self.assertIsNone(safe_next_path("//evil.example/x"))
        self.assertIsNone(safe_next_path("https://evil.example"))
        self.assertIsNone(safe_next_path("/\\evil.example"))
        self.assertIsNone(safe_next_path("/ok\r\nSet-Cookie: x=1"))


class TestGetAppLanding(TestCase):
    ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"
    IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"

    def get(self, query="", agent=""):
        return self.client.get("/get-app/" + query, HTTP_USER_AGENT=agent)

    def test_offers_both_stores_on_other_devices_and_continues_in_the_browser(self):
        response = self.get("?next=%2Fschedule-flight%3FcontestId%3D1%26navigationTaskId%3D2")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Get it on Google Play")
        self.assertContains(response, "Get it on the App Store")
        self.assertContains(response, "Continue in the browser")
        self.assertContains(response, "/schedule-flight?contestId=1&amp;navigationTaskId=2")

    def test_android_gets_play_with_the_install_referrer_and_iphone_gets_the_app_store(self):
        android = self.get("?next=%2Fschedule-flight%3FcontestId%3D1", agent=self.ANDROID)
        self.assertContains(android, "Get it on Google Play")
        self.assertNotContains(android, "Get it on the App Store")
        # The registration target survives the install: referrer=next%3D%252Fschedule-flight%253FcontestId%253D1
        self.assertContains(android, "referrer=next%3D%252Fschedule-flight%253FcontestId%253D1")
        iphone = self.get("?next=%2Fschedule-flight", agent=self.IPHONE)
        self.assertContains(iphone, "Get it on the App Store")
        self.assertNotContains(iphone, "Get it on Google Play")

    def test_a_link_to_another_site_is_not_offered(self):
        response = self.get("?next=https%3A%2F%2Fevil.example")
        self.assertNotContains(response, "Continue in the browser")
        self.assertNotContains(response, "evil.example")


class TestWellKnownFiles(TestCase):
    def test_android_asset_links_are_empty_until_the_fingerprints_are_configured(self):
        self.assertEqual(self.client.get("/.well-known/assetlinks.json").json(), [])

    @override_settings(MOBILE_ANDROID_CERT_SHA256=["AA:BB"], MOBILE_ANDROID_PACKAGE="no.example.app")
    def test_android_asset_links_name_the_app_and_its_certificates(self):
        statement = self.client.get("/.well-known/assetlinks.json").json()[0]
        self.assertEqual(statement["relation"], ["delegate_permission/common.handle_all_urls"])
        self.assertEqual(statement["target"]["package_name"], "no.example.app")
        self.assertEqual(statement["target"]["sha256_cert_fingerprints"], ["AA:BB"])

    def test_ios_association_is_empty_until_the_app_id_is_configured(self):
        self.assertEqual(self.client.get("/.well-known/apple-app-site-association").json(), {"applinks": {"details": []}})

    @override_settings(MOBILE_IOS_APP_ID="TEAM123.no.airports.ios.livetracking")
    def test_ios_association_opens_the_get_app_links_in_the_app(self):
        details = self.client.get("/.well-known/apple-app-site-association").json()["applinks"]["details"]
        self.assertEqual(details[0]["appIDs"], ["TEAM123.no.airports.ios.livetracking"])
        self.assertEqual(details[0]["components"], [{"/": "/get-app/*"}])


class TestGetAppLink(TestCase):
    def test_wraps_the_registration_page_in_a_get_app_link(self):
        request = RequestFactory().get("/", HTTP_HOST="app.airsports.no", **{"wsgi.url_scheme": "https"})
        self.assertEqual(
            get_app_link(request, "/display/navigationtask/5/quick_register/"),
            "https://app.airsports.no/get-app/?next=%2Fdisplay%2Fnavigationtask%2F5%2Fquick_register%2F",
        )
