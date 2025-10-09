from celery import shared_task
from django.utils import timezone
from base_stripe.models.events import StripeWebhookEvent
from base.models.utility.error import Error, Log, EnvHelper

from base_stripe.models.payment_models import StripeCustomer
from base_stripe.models.payment_models import StripeInvoice
from base_stripe.models.payment_models import StripeSubscription
from base_stripe.models.payment_models import StripeCheckoutSession

from the_hangar_hub.models.rental_models import Tenant, RentalInvoice, RentalAgreement

from base_stripe.services import webhook_service
from the_hangar_hub.models import Tenant

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
        event = StripeWebhookEvent.objects.select_for_update().get(id=webhook_record_id)

        # Idempotency check
        if event.processed:
            log.info(f"Event {webhook_record_id} already processed, skipping")
            return f"Event {webhook_record_id} already processed"

        # Sync local model with Stripe data
        refreshed = webhook_service.stripe_model_refresh(event)

        # Some objects do not require any additional processing
        ignore = [
            "payment_intent", "invoiceitem", "credit_note",
            "setup_intent", "charge", "payment_method",
            "checkout.session", "capability",
        ]
        if event.object_type in ignore:
            processed = True  # Mark as processed so it can be ignored/deleted from the table

        elif not refreshed:
            # Likely not a known object type yet.
            # If is known type, cannot process with old data.
            log.info(f"Not processing un-refreshed object: {event.object_type}")
            processed = False

        else:
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

        # Record refreshed/processed state
        event.refreshed = refreshed or False
        event.processed = processed or False
        event.save()
        
        log.info(f"Processed event {webhook_record_id}")
        return f"Processed event {webhook_record_id}"

    except StripeWebhookEvent.DoesNotExist:
        log.error(f"Event {webhook_record_id} not found")
        return f"Event {webhook_record_id} not found"

    except Exception as exc:
        log.error(f"Error processing event {webhook_record_id}: {str(exc)}")

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


def handle_customer_event(event):
    try:
        if event.event_type == "customer.created":
            customer = StripeCustomer.from_stripe_id(event.object_id)
            if customer:
                # Check for tenant that needs to be updated
                for t in Tenant.objects.filter(customer__isnull=True, contact__email__iexact=customer.email):
                    t.customer = customer
                    t.save()

        return True
    except Exception as ee:
        Error.record(ee, event)
        return False


def handle_invoice_event(event):
    try:
        invoice = StripeInvoice.from_stripe_id(event.object_id)
        if invoice:
            # Is invoice tied to a RentalAgreement?
            if invoice.related_type == "RentalAgreement":
                rental_agreement_id = invoice.related_id
            elif invoice.subscription and invoice.subscription.related_type == "RentalAgreement":
                rental_agreement_id = invoice.subscription.related_id
            elif "RentalAgreement" in invoice.metadata:
                rental_agreement_id = invoice.metadata.get("RentalAgreement")
            elif invoice.subscription and invoice.subscription.metadata and "RentalAgreement" in invoice.subscription.metadata:
                rental_agreement_id = invoice.subscription.metadata.get("RentalAgreement")
            else:
                rental_agreement_id = None

            if rental_agreement_id:
                rental_agreement = RentalAgreement.get(rental_agreement_id)
                # ToDo: Make sure invoice exists for rental_agreement

            else:
                # ToDo: Maybe a HangarHub subscription?
                pass


            if event.event_type == "invoice.created":
                # ToDo: Send an email?
                pass

            return True

        else:  # No invoice record
            return False
    except Exception as ee:
        Error.record(ee, event)
        return False


def handle_subscription_event(event):
    # Probably need to do something...
    return False


def handle_checkout_session_event(event):
    # Would result in a new subscription, so probably nothing needed???
    return True

