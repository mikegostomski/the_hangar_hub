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


def react_to_events():
    """
    Webhook events get recorded to the Django database.
    This endpoint refreshes any models tied to the objects in those events
    (customers, subscriptions, and invoices)
    """
    webhook_events = WebhookEvent.objects.filter(refreshed=False)
    processed_object_ids = []
    processed_events = []

    # Some objects are currently not being tracked locally
    ignore = [
        "payment_intent", "invoiceitem", "credit_note",
        "setup_intent", "charge", "payment_method",
        "checkout.session",
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
                if Invoice.from_stripe_id(event.object_id):
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
                inv = Invoice.from_stripe_id(event.object_id)
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

            # If a new subscription was created, insert a local record to track it
            if event_type == "created":
                if Subscription.from_stripe_id(event.object_id):
                    processed_object_ids.append(event.object_id)
                    processed_events.append(event)
                continue

            # If object processed as insert, data is current and does not need to be updated
            elif event.object_id in processed_object_ids:
                processed_events.append(event)
                continue

            # Refresh subscription with latest data
            else:
                sub = Subscription.from_stripe_id(event.object_id)
                if sub.sync():
                    processed_object_ids.append(event.object_id)
                    processed_events.append(event)
                continue


    # Mark Webhook Events as "refreshed"
    try:
        if processed_events:
            for whe in processed_events:
                whe.refreshed = True
            WebhookEvent.objects.bulk_update(processed_events, ['refreshed'])
    except Exception as ee:
        Error.record(ee)

    return {
        "processed_events": len(processed_events),
    }

