from django.http import HttpResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from base_stripe.services import price_service, accounts_service
from base.services import message_service
from django.views.decorators.csrf import csrf_exempt
import json
import stripe
from base_stripe.classes.webhook_validation import WebhookValidation
from base_stripe.models.events import WebhookEvent
from base.models.utility.error import Error

log = Log()
env = EnvHelper()

# ToDo: Error Handling/Messages


@csrf_exempt
def webhook(request):
    result = WebhookValidation.validate(request)
    if result.ignore or not result.valid_request:
        return HttpResponse(status=result.status_code)

    try:

        # Return success response
        return HttpResponse(status=200)

    except Exception as ee:
        Error.record(ee)
        return HttpResponse(status=500)


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

def show_accounts(request):
    accounts = accounts_service.get_connected_accounts()
    return render(
        request, "base/stripe/accounts/index.html",
        {
            "accounts": accounts,
        }
    )

def modify_account(request):
    account_id = request.POST.get("account_id")
    account = accounts_service.get_connected_account(account_id)
    if not account:
        message_service.post_error("Connected account could not be retrieved from Stripe")
        return HttpResponseForbidden()

    something = False
    for attr in account.editable_attrs():
        if attr in request.POST:
            value = request.POST.get(attr)
            if attr == "company_phone":
                account.set_phone(value)
                something = True
            elif hasattr(account, attr):
                setattr(account, attr, value)
                something = True
            elif attr in account.company_address:
                account.company_address[attr] = value
                something = True
            else:
                log.error(f"{attr} does not exist in the account object or {account.company_address}")

    if not something:
        log.debug(request.POST)
        message_service.post_error("Nothing was updated.")
        return HttpResponseForbidden()

    if accounts_service.modify_connected_account(account):
        message_service.post_success("Account has been updated")
        return HttpResponse("ok")

    return HttpResponseForbidden()


