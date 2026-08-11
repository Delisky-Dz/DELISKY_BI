from django.conf import settings
from django.shortcuts import (
    redirect,
    render,
)
from django.views.decorators.http import (
    require_http_methods,
)

from .forms import JobApplicationForm
from .turnstile import verify_turnstile


def _turnstile_context():
    return {
        "turnstile_enabled": (
            settings.TURNSTILE_ENABLED
        ),
        "turnstile_site_key": (
            settings.TURNSTILE_SITE_KEY
        ),
    }


@require_http_methods(
    ["GET", "POST"]
)
def application_form(request):
    language = getattr(
        request,
        "LANGUAGE_CODE",
        "ar",
    )

    if request.method == "POST":
        form = JobApplicationForm(
            request.POST,
            request.FILES,
            language=language,
        )

        if form.is_valid():
            turnstile_valid = True

            if settings.TURNSTILE_ENABLED:
                token = request.POST.get(
                    "cf-turnstile-response",
                    "",
                )

                turnstile_valid = (
                    verify_turnstile(token)
                )

            if turnstile_valid:
                form.save()

                return redirect(
                    "recruitment_public:success"
                )

            if language == "ar":
                message = (
                    "\u1578\u1593\u1584\u1585 "
                    "\u1575\u1604\u1578\u1581\u1602\u1602 "
                    "\u1605\u1606 "
                    "\u1571\u1606\u1603 "
                    "\u1605\u1587\u1578\u1582\u1583\u1605 "
                    "\u1581\u1602\u1610\u1602\u1610. "
                    "\u1581\u1575\u1608\u1604 "
                    "\u1605\u1585\u1577 "
                    "\u1571\u1582\u1585\u1609."
                )
            else:
                message = (
                    "We could not verify that you are "
                    "a real user. Please try again."
                )

            form.add_error(
                None,
                message,
            )

    else:
        form = JobApplicationForm(
            language=language,
        )

    context = {
        "form": form,
        **_turnstile_context(),
    }

    return render(
        request,
        "recruitment/application_form.html",
        context,
    )


def application_success(request):
    return render(
        request,
        "recruitment/application_success.html",
    )
