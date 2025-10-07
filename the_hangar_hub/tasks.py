from celery import shared_task
from django.utils import timezone
from base_stripe.models.events import WebhookEvent
from base.models.utility.error import Error, Log, EnvHelper
from base_stripe.models.payment_models import Customer, Invoice, Subscription, CheckoutSession

log = Log()
env = EnvHelper()


@shared_task(bind=True, max_retries=3)
def process_stripe_event(self, webhook_record_id):
    """
    Process a Stripe webhook event

    This happens asynchronously, and will not be logged with the standard web logging

    Logs appear in the console running celery:
        celery -A the_hangar_hub worker --loglevel=info --pool=solo

    The returned values can be viewed via "flower"
        pip install flower
        celery -A the_hangar_hub flower
        Access at: http://localhost:5555
    """
    event = None
    log.debug(f"\n{'='*80}\nwebhook_record_id: {webhook_record_id}\n{'='*80}")
    try:
        event = WebhookEvent.objects.select_for_update().get(id=webhook_record_id)

        # Idempotency check
        if event.processed:
            log.info(f"Event {webhook_record_id} already processed, skipping")
            return f"Event {webhook_record_id} already processed"

        # Some objects are currently not being tracked locally
        ignore = [
            "payment_intent", "invoiceitem", "credit_note",
            "setup_intent", "charge", "payment_method",
            "checkout.session", "capability",
        ]
        if event.object_type in ignore:
            log.info(f"Event {webhook_record_id} can be ignored ({event.object_type})")
            return f"Event {webhook_record_id} can be ignored ({event.object_type})"

        log.info(f"Processing event {webhook_record_id} of type {event.event_type}")

        # Route to appropriate handler
        processed = False
        if event.object_type == 'customer':
            processed = handle_customer_event(event)
        elif event.object_type == 'invoice':
            processed = handle_invoice_event(event)
        elif event.object_type == 'subscription':
            processed = handle_subscription_event(event)
        elif event.object_type == 'checkout.session':
            processed = handle_checkout_session_event(event)

        # Add more event types as needed

        # Mark as processed
        event.refreshed = True
        event.processed = processed or False
        event.save()
        
        log.info(f"Successfully processed event {webhook_record_id}")
        return f"Successfully processed event {webhook_record_id}"

    except WebhookEvent.DoesNotExist:
        log.error(f"Event {webhook_record_id} not found")
        return f"Event {webhook_record_id} not found"

    except Exception as exc:
        log.error(f"Error processing event {webhook_record_id}: {str(exc)}")

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


def handle_customer_event(event):
    # If a customer was deleted
    if event.event_type == "deleted":
        cust = Customer.get(event.object_id)
        if cust:
            log.info(f"Deleting customer #{cust.id}: {event.object_id}")
            cust.status = "deleted"
            cust.save()
        return True

    # Refresh customer with latest data
    else:
        cust = Customer.get_or_create(stripe_id=event.object_id)
        return cust.sync()


def handle_invoice_event(event):
    if event.event_type == "deleted":
        del_inv = Invoice.get(event.object_id)
        if del_inv:
            log.info(f"Invoice #{del_inv.id} was deleted in Stripe: {event.object_id}")
            del_inv.status = "deleted"
            del_inv.save()
        return True

    # Refresh invoice with latest data
    else:
        inv = Invoice.from_stripe_id(event.object_id)
        return inv.sync()


def handle_subscription_event(event):
    log.info(f"handle_subscription_event({event.object_id})")
    sub = Subscription.from_stripe_id(event.object_id)
    log.info(f"sub: {sub}")
    return sub.sync()


def handle_checkout_session_event(event):
    co = CheckoutSession.from_stripe_id(event.object_id)
    return co.sync()

