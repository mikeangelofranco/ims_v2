from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.views.csrf import csrf_failure as default_csrf_failure


def csrf_failure(request, reason=""):
    # A form opened before local cookie configuration changed has no current
    # CSRF cookie. Reject the POST and obtain a fresh form; never replay it.
    if (
        settings.DEBUG
        and request.path == reverse("onboarding:sign_in")
        and reason == "CSRF cookie not set."
    ):
        response = redirect(f"{request.path}?csrf_retry=1")
        response["Cache-Control"] = "no-store"
        return response
    return default_csrf_failure(request, reason=reason)
