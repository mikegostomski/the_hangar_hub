from base.classes.util.env_helper import Log, EnvHelper
from base_stripe.models.events import StripeWebhookEvent
from base.models.utility.error import Error
from base_stripe.models.payment_models import StripeInvoice, StripeCustomer, StripeSubscription, StripeCheckoutSession
from base_stripe.models.product_models import StripeProduct, StripePrice
from base_stripe.models.connected_account import StripeConnectedAccount


log = Log()
env = EnvHelper()

# ToDo: Error Handling/Messages


def stripe_model_refresh(webhook_event_instance):
    """
    From a stripe object-type and ID, create or refresh the Django model representation of the object
    """
    # Some objects are currently not being tracked locally
    ignore = [
        "payment_intent", "invoiceitem", "credit_note",
        "setup_intent", "charge", "payment_method",
        "capability"
    ]
    if webhook_event_instance.object_type in ignore:
        return True  # Mark as refreshed so they can be ignored/deleted from the table

    # Route to appropriate handler
    refreshed = False
    try:
        if webhook_event_instance.object_type == 'customer':
            refreshed = _handle_customer_event(webhook_event_instance)
        elif webhook_event_instance.object_type == 'invoice':
            refreshed = _handle_invoice_event(webhook_event_instance)
        elif webhook_event_instance.object_type == 'subscription':
            refreshed = _handle_subscription_event(webhook_event_instance)
        elif webhook_event_instance.object_type == 'checkout.session':
            refreshed = _handle_checkout_session_event(webhook_event_instance)
        elif webhook_event_instance.object_type == 'product':
            refreshed = _handle_product_event(webhook_event_instance)
        elif webhook_event_instance.object_type == 'price':
            refreshed = _handle_price_event(webhook_event_instance)
        elif webhook_event_instance.object_type == 'account':
            refreshed = _handle_account_event(webhook_event_instance)

    except Exception as ee:
        Error.record(ee, webhook_event_instance)
    return refreshed


def _handle_customer_event(event):
    # If a customer was deleted
    if event.event_type == "deleted":
        cust = StripeCustomer.get(event.object_id)
        if cust:
            log.info(f"Deleting customer #{cust.id}: {event.object_id}")
            cust.status = "deleted"
            cust.save()
        return True

    # Refresh customer with latest data
    else:
        cust = StripeCustomer.get_or_create(stripe_id=event.object_id)
        return cust.sync()


def _handle_invoice_event(event):
    if event.event_type == "deleted":
        del_obj = StripeInvoice.get(event.object_id)
        if del_obj:
            log.info(f"{del_obj} was deleted in Stripe: {event.object_id}")
            del_obj.deleted = True
            del_obj.save()
        return True

    # Refresh invoice with latest data
    else:
        inv = StripeInvoice.from_stripe_id(event.object_id)
        return inv.sync()


def _handle_subscription_event(event):
    if event.event_type == "deleted":
        del_obj = StripeSubscription.get(event.object_id)
        if del_obj:
            log.info(f"{del_obj} was deleted in Stripe: {event.object_id}")
            del_obj.deleted = True
            del_obj.save()
        return True
    log.info(f"handle_subscription_event({event.object_id})")
    sub = StripeSubscription.from_stripe_id(event.object_id)
    log.info(f"sub: {sub}")
    return sub.sync()


def _handle_checkout_session_event(event):
    if event.event_type == "deleted":
        del_obj = StripeCheckoutSession.get(event.object_id)
        if del_obj:
            log.info(f"{del_obj} was deleted in Stripe: {event.object_id}")
            del_obj.deleted = True
            del_obj.save()
        return True
    co = StripeCheckoutSession.from_stripe_id(event.object_id)
    return co.sync()

def _handle_product_event(event):
    if event.event_type == "product.deleted":
        del_obj = StripeProduct.get(event.object_id)
        if del_obj:
            log.info(f"{del_obj} was deleted in Stripe: {event.object_id}")
            del_obj.deleted = True
            del_obj.save()
        return True
    co = StripeProduct.from_stripe_id(event.object_id)
    return co.sync()

def _handle_price_event(event):
    if event.event_type == "price.deleted":
        del_obj = StripePrice.get(event.object_id)
        if del_obj:
            log.info(f"{del_obj} was deleted in Stripe: {event.object_id}")
            del_obj.deleted = True
            del_obj.save()
        return True
    co = StripePrice.from_stripe_id(event.object_id)
    return co.sync()

def _handle_account_event(event):
    if event.event_type == "account.deleted":
        del_obj = StripeConnectedAccount.get(event.object_id)
        if del_obj:
            log.info(f"{del_obj} was deleted in Stripe: {event.object_id}")
            del_obj.deleted = True
            del_obj.save()
        return True
    co = StripeConnectedAccount.from_stripe_id(event.object_id)
    return co.sync()






# ToDo: Should not be needed anymore:
def react_to_events():
    """
    Webhook events get recorded to the Django database.
    This endpoint refreshes any models tied to the objects in those events
    (customers, subscriptions, and invoices)
    """
    webhook_events = StripeWebhookEvent.objects.filter(refreshed=False)
    processed_object_ids = []
    processed_events = []

    # Some objects are currently not being tracked locally
    ignore = [
        "payment_intent", "invoiceitem", "credit_note",
        "setup_intent", "charge", "payment_method",
        "checkout.session", "capability",
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
                if StripeInvoice.from_stripe_id(event.object_id):
                    processed_object_ids.append(event.object_id)
                    processed_events.append(event)
                continue

            # If a draft invoice was deleted
            elif event_type == "deleted":
                del_inv = StripeInvoice.get(event.object_id)
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
                inv = StripeInvoice.from_stripe_id(event.object_id)
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
                if StripeCustomer.get_or_create(stripe_id=event.object_id):
                    processed_object_ids.append(event.object_id)
                    processed_events.append(event)
                continue

            # If a customer was deleted
            elif event_type == "deleted":
                cust = StripeCustomer.get(event.object_id)
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
                cust = StripeCustomer.get_or_create(stripe_id=event.object_id)
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
                if StripeSubscription.from_stripe_id(event.object_id):
                    processed_object_ids.append(event.object_id)
                    processed_events.append(event)
                continue

            # If object processed as insert, data is current and does not need to be updated
            elif event.object_id in processed_object_ids:
                processed_events.append(event)
                continue

            # Refresh subscription with latest data
            else:
                sub = StripeSubscription.from_stripe_id(event.object_id)
                if sub.sync():
                    processed_object_ids.append(event.object_id)
                    processed_events.append(event)
                continue

        """
        CONNECTED_ACCOUNTS
        """
        if object_type == "account":
            ca = StripeConnectedAccount.from_stripe_id(event.object_id)
            if ca and ca.sync():
                processed_object_ids.append(event.object_id)
                processed_events.append(event)
            continue

    # Mark Webhook Events as "refreshed"
    try:
        if processed_events:
            for whe in processed_events:
                whe.refreshed = True
            StripeWebhookEvent.objects.bulk_update(processed_events, ['refreshed'])
    except Exception as ee:
        Error.record(ee)

    return {
        "processed_events": len(processed_events),
    }

