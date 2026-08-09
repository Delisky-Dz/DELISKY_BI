from django.test import TestCase


class PublicWebsiteLanguageTests(TestCase):
    def test_arabic_home_is_available_and_rtl(self):
        response = self.client.get("/ar/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="ar"')
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, 'href="/en/"')

    def test_english_home_is_available_and_ltr(self):
        response = self.client.get("/en/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="en"')
        self.assertContains(response, 'dir="ltr"')
        self.assertContains(response, 'href="/ar/"')

    def test_existing_login_route_stays_unprefixed(self):
        response = self.client.get("/login/")

        self.assertNotEqual(response.status_code, 404)

    def test_home_contains_main_corporate_sections(self):
        response = self.client.get("/en/")

        self.assertContains(response, 'id="about"')
        self.assertContains(response, 'id="activity"')
        self.assertContains(response, 'class="business-grid"')
        self.assertContains(response, 'id="fleet"')
        self.assertContains(response, 'id="coverage"')
