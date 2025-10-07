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
from base.decorators import require_authority, require_authentication, report_errors
from base_stripe.models.payment_models import Invoice, Customer, Subscription
from base_stripe.services import webhook_service, config_service
from the_hangar_hub.tasks import process_stripe_event


log = Log()
env = EnvHelper()

# ToDo: Error Handling/Messages


@csrf_exempt
def webhook(request):
    result = WebhookValidation.validate(request)
    if result.ignore or not result.valid_request:
        return HttpResponse(status=result.status_code)

    try:
        # Queue the task for async processing
        process_stripe_event.delay(result.webhook_event_id)
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


def react_to_events(request):
    """
    Webhook events get recorded to the Django database.
    This endpoint refreshes any models tied to the objects in those events
    (customers, subscriptions, and invoices)
    """
    return JsonResponse(webhook_service.react_to_events())

def reset_sandbox(request):
    """
    Delete test customers and subscriptions from sandbox
    """
    if env.is_prod:
        log.error("Cannot delete test data in production")
        return HttpResponseForbidden()

    config_service.set_stripe_api_key()

    # 1. Cancel all active subscriptions
    for sub in stripe.Subscription.list(status='active', limit=100).auto_paging_iter():
        stripe.Subscription.delete(sub.id)

    # 2. Delete all customers
    for cust in stripe.Customer.list(limit=100).auto_paging_iter():
        stripe.Customer.delete(cust.id)

    return HttpResponse("Completed")



def show_prices(request):
    prices = price_service.get_price_list()
    return render(
        request, "base/stripe/prices/index.html",
        {
            "prices": prices,
        }
    )

def show_accounts(request):
    return HttpResponseForbidden()


def modify_account(request):
    return HttpResponseForbidden()


