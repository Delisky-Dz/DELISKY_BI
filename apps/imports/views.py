from django.shortcuts import render

from .access import accountant_required


@accountant_required
def accountant_home(request):
    return render(
        request,
        "imports/accountant_home.html",
    )
