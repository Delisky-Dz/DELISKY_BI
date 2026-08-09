from django.shortcuts import (
    redirect,
    render,
)
from django.views.decorators.http import (
    require_http_methods,
)

from .forms import JobApplicationForm


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
            form.save()

            return redirect(
                "recruitment_public:success"
            )

    else:
        form = JobApplicationForm(
            language=language,
        )

    return render(
        request,
        "recruitment/application_form.html",
        {
            "form": form,
        },
    )


def application_success(request):
    return render(
        request,
        "recruitment/application_success.html",
    )
