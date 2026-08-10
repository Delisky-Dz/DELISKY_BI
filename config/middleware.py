from django.http import HttpResponseNotFound
from django.shortcuts import redirect


class ProductionHostSeparationMiddleware:
    """
    Keep the public website and the private application separated by host.

    This middleware is enabled only from production settings.
    """

    PUBLIC_HOSTS = {
        "delisky-dz.com",
        "www.delisky-dz.com",
    }

    PRIVATE_HOSTS = {
        "app.delisky-dz.com",
    }

    LOCAL_HOSTS = {
        "127.0.0.1",
        "localhost",
    }

    PUBLIC_PATHS = {
        "/",
        "/ar/",
        "/en/",
    }

    PUBLIC_PREFIXES = (
        "/ar/careers/",
        "/en/careers/",
        "/static/",
    )

    PRIVATE_PATHS = {
        "/login/",
        "/logout/",
        "/account/route/",
    }

    PRIVATE_PREFIXES = (
        "/admin/",
        "/manager/",
        "/accountant/",
        "/static/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":", 1)[0].lower()
        path = request.path

        if host in self.LOCAL_HOSTS:
            return self.get_response(request)

        if host in self.PUBLIC_HOSTS:
            if self._is_public_path(path):
                return self.get_response(request)

            return HttpResponseNotFound("Not Found")

        if host in self.PRIVATE_HOSTS:
            if path == "/":
                return redirect("accounts:login")

            if self._is_private_path(path):
                return self.get_response(request)

            return HttpResponseNotFound("Not Found")

        return HttpResponseNotFound("Not Found")

    @classmethod
    def _is_public_path(cls, path):
        if path in cls.PUBLIC_PATHS:
            return True

        return path.startswith(cls.PUBLIC_PREFIXES)

    @classmethod
    def _is_private_path(cls, path):
        if path in cls.PRIVATE_PATHS:
            return True

        return path.startswith(cls.PRIVATE_PREFIXES)
