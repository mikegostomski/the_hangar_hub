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
    processed_object_ids = []
    processed_events = []

    # Some objects are currently not being tracked locally
    ignore = [
        "payment_intent",
    ]

    for event in webhook_events:
        object_type = event.object_type
        parts = event.event_type.split(".")
        event_type = parts[len(parts)-1]

        # Some objects are currently not being tracked locally
        if object_type in ignore:
            processed_events.append(event)
            continue

        """
        INVOICES
        """
        if object_type == "invoice":
            # If a new invoice was created, insert a local record to track it
            if event_type == "created":
                if Invoice.create_from_stripe(event.object_id):
                    processed_object_ids.append(event.object_id)
                    processed_events.append(event)
                continue

            # If a draft invoice was deleted
            elif event_type == "deleted":
                del_inv = Invoice.get(event.object_id)
                if del_inv:
                    log.info(f"Invoice #{del_inv.id} was deleted in Stripe: {event.object_id}")
                    del_inv.status = "deleted"
                    del_inv.save()
                    processed_object_ids.append(event.object_id)
                    processed_events.append(event)
                continue

            # If object processed as insert or delete, data is current and does not need to be updated
            elif event.object_id in processed_object_ids:
                processed_events.append(event)
                continue

            # Refresh invoice with latest data
            else:
                # The create function will return an existing record, or create if needed
                inv = Invoice.create_from_stripe(event.object_id)
                if inv.sync():
                    log.debug(f"UPDATING INVOICE {event.object_id}")
                    processed_object_ids.append(event.object_id)
                    processed_events.append(event)
                continue


        """
        CUSTOMERS
        """
        if object_type == "customer":
            # If a new customer was created, insert a local record to track it
            if event_type == "created":
                if Customer.get_or_create(stripe_id=event.object_id):
                    processed_object_ids.append(event.object_id)
                    processed_events.append(event)
                continue

            # If a customer was deleted
            elif event_type == "deleted":
                cust = Customer.get(event.object_id)
                if cust:
                    log.info(f"Deleting customer #{cust.id}: {event.object_id}")
                    cust.status = "deleted"
                    cust.save()
                    processed_object_ids.append(event.object_id)
                    processed_events.append(event)
                continue

            # If object processed as insert or delete, data is current and does not need to be updated
            elif event.object_id in processed_object_ids:
                processed_events.append(event)
                continue

            # Refresh customer with latest data
            else:
                cust = Customer.get_or_create(stripe_id=event.object_id)
                if cust.sync():
                    processed_object_ids.append(event.object_id)
                    processed_events.append(event)
                continue


        """
        SUBSCRIPTIONS
        """
        if object_type == "subscription":
            continue


    # Mark Webhook Events as "refreshed"
    try:
        if processed_events:
            for whe in processed_events:
                whe.refreshed = True
            WebhookEvent.objects.bulk_update(webhook_events, ['refreshed'])
    except Exception as ee:
        Error.record(ee)

    return JsonResponse({
        "processed_events": len(webhook_events),
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


