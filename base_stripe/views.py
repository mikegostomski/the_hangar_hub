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
from base_stripe.models.invoice import Invoice
from base_stripe.models.customer import Customer
from base_stripe.models.subscription import Subscription


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


def react_to_events(request):
    """
    Webhook events get recorded to the Django database.
    This endpoint refreshes any models tied to the objects in those events
    (customers, subscriptions, and invoices)
    """
    affected_objects = {}
    webhook_events = WebhookEvent.objects.filter(refreshed=False)
    for event in webhook_events:
        if event.object_type not in affected_objects:
            affected_objects[event.object_type] = []
        affected_objects[event.object_type].append(event.object_id)

    # Only need to update object types that have associated models
    updated_counts = {
        "customer": 0,
        "subscription": 0,
        "invoice": 0,
        "webhook_events": 0,
    }
    error_counts = {
        "customer": 0,
        "subscription": 0,
        "invoice": 0,
        "webhook_events": 0,
    }

    # CUSTOMERS
    for customer_id in list(set(affected_objects.get("customer") or [])):
        try:
            customer_model = Customer.get(customer_id)
            if not customer_model:
                customer_model = Customer()
                customer_model.stripe_id = customer_id
                # Sync() will fill in the rest
            customer_model.sync()
            customer_model.save()
            updated_counts["customer"] += 1
        except Exception as ee:
            Error.record(ee, customer_id)
            error_counts["customer"] += 1

    # SUBSCRIPTIONS
    for subscription_id in list(set(affected_objects.get("subscription") or [])):
        try:
            subscription_model = Subscription.get(subscription_id)
            if not subscription_model:
                subscription_model = Subscription()
                subscription_model.stripe_id = subscription_id
                # Sync() will fill in the rest
            subscription_model.sync()
            subscription_model.save()
            updated_counts["subscription"] += 1
        except Exception as ee:
            Error.record(ee, subscription_id)
            error_counts["subscription"] += 1

    # INVOICES
    for invoice_id in list(set(affected_objects.get("invoice") or [])):
        try:
            invoice_model = Invoice.get(invoice_id)
            if not invoice_model:
                invoice_model = Invoice()
                invoice_model.stripe_id = invoice_id
                # Sync() will fill in the rest
            invoice_model.sync()
            invoice_model.save()
            updated_counts["invoice"] += 1
        except Exception as ee:
            Error.record(ee, invoice_id)
            error_counts["invoice"] += 1

    # Mark Webhook Events as "refreshed"
    try:
        for whe in webhook_events:
            whe.refreshed = True
        WebhookEvent.objects.bulk_update(webhook_events, ['refreshed'])
        updated_counts["webhook_events"] = len(webhook_events)
    except Exception as ee:
        Error.record(ee)
        error_counts["webhook_events"] = len(webhook_events)

    return JsonResponse({
        "updated": updated_counts,
        "errors": error_counts,
    })


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


