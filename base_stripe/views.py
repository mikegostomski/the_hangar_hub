from django.http import HttpResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from base_stripe.services import price_service

log = Log()
env = EnvHelper()

# ToDo: Error Handling/Messages


def home(request, file_id):
    """
    Retrieve a specified file and display as attachment.

    Security:
    This will only display files belonging to the authenticated owner, or files
    whose ID is saved in the session.  This prevents a user from changing the
    URL to display any file in the database.

    File IDs are automatically added to the session by the {%file_preview%} tag.
    Each app must verify permissions before displaying a file preview to a user.

    Authenticated users can always use this to view their own files
    """
    log.trace()

    return HttpResponse("Hello")


def show_prices(request):
    prices = price_service.get_price_list()
    return render(
        request, "base/stripe/prices/index.html",
        {
            "prices": prices,
        }
    )