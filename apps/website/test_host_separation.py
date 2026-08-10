from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from config.middleware import ProductionHostSeparationMiddleware


@override_settings(
    ALLOWED_HOSTS=[
        "delisky-dz.com",
        "www.delisky-dz.com",
        "app.delisky-dz.com",
        "127.0.0.1",
        "localhost",
    ]
)
class ProductionHostSeparationMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ProductionHostSeparationMiddleware(
            lambda request: HttpResponse("PASSED")
        )

    def request(self, host, path):
        request = self.factory.get(
            path,
            HTTP_HOST=host,
        )
        return self.middleware(request)

    def test_public_host_allows_public_routes(self):
        paths = [
            "/",
            "/ar/",
            "/en/",
            "/ar/careers/apply/",
            "/en/careers/apply/",
            "/static/website/css/site.css",
        ]

        for path in paths:
            with self.subTest(path=path):
                response = self.request(
                    "www.delisky-dz.com",
                    path,
                )
                self.assertEqual(
                    response.status_code,
                    200,
                )

    def test_public_host_blocks_private_routes(self):
        paths = [
            "/login/",
            "/manager/",
            "/accountant/recruitment/",
            "/admin/",
            "/media/recruitment/cv/test.pdf",
        ]

        for path in paths:
            with self.subTest(path=path):
                response = self.request(
                    "www.delisky-dz.com",
                    path,
                )
                self.assertEqual(
                    response.status_code,
                    404,
                )

    def test_private_host_allows_private_routes(self):
        paths = [
            "/login/",
            "/logout/",
            "/account/route/",
            "/manager/",
            "/accountant/recruitment/",
            "/admin/",
            "/static/admin/css/base.css",
        ]

        for path in paths:
            with self.subTest(path=path):
                response = self.request(
                    "app.delisky-dz.com",
                    path,
                )
                self.assertEqual(
                    response.status_code,
                    200,
                )

    def test_private_host_blocks_public_routes(self):
        paths = [
            "/ar/",
            "/en/",
            "/ar/careers/apply/",
            "/en/careers/apply/",
            "/media/recruitment/cv/test.pdf",
        ]

        for path in paths:
            with self.subTest(path=path):
                response = self.request(
                    "app.delisky-dz.com",
                    path,
                )
                self.assertEqual(
                    response.status_code,
                    404,
                )

    def test_private_root_redirects_to_login(self):
        response = self.request(
            "app.delisky-dz.com",
            "/",
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertEqual(
            response["Location"],
            "/login/",
        )

    def test_apex_domain_is_public(self):
        response = self.request(
            "delisky-dz.com",
            "/ar/",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_local_hosts_remain_available(self):
        for host in (
            "127.0.0.1",
            "localhost",
        ):
            with self.subTest(host=host):
                response = self.request(
                    host,
                    "/manager/",
                )
                self.assertEqual(
                    response.status_code,
                    200,
                )

    def test_production_settings_enable_middleware(self):
        production_file = (
            Path(settings.BASE_DIR)
            / "config"
            / "settings"
            / "production.py"
        )

        content = production_file.read_text(
            encoding="utf-8",
        )

        self.assertIn(
            "config.middleware."
            "ProductionHostSeparationMiddleware",
            content,
        )
