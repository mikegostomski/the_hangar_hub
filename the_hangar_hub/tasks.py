from celery import shared_task
from django.utils import timezone
from base_stripe.models.events import StripeWebhookEvent
from base.models.utility.error import Error, Log, EnvHelper

from base_stripe.models.payment_models import StripeCustomer
from base_stripe.models.payment_models import StripeInvoice
from base_stripe.models.payment_models import StripeSubscription
from base_stripe.models.payment_models import StripeCheckoutSession
import stripe

from the_hangar_hub.models.rental_models import Tenant, RentalInvoice, RentalAgreement

from base_stripe.services import webhook_service
from base_stripe.services.config_service import set_stripe_api_key
from the_hangar_hub.models import Tenant, Airport

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

    # Objects that must be refreshed (sync) before being processed
    refresh_required = [
        "customer", "invoice", "subscription",
        "checkout.session", "account",
    ]

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

        elif (not refreshed) and event.object_type in refresh_required:
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
            elif event.object_type == 'invoice_payment':
                processed = handle_invoice_payment_event(event)

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
        # Nothing to do???
        return True
    except Exception as ee:
        Error.record(ee, event)
        return False


def handle_invoice_event(event):
    log.debug(f"CELERY::: Handle Invoice: {event.object_id}")
    try:
        invoice = StripeInvoice.from_stripe_id(event.object_id, event.account_id)
        log.debug(f"CELERY::: Invoice Model: {invoice}")
        if invoice and not invoice.deleted:
            # Is invoice tied to a RentalAgreement?
            if invoice.related_type == "RentalAgreement":
                rental_agreement_id = invoice.related_id
            elif invoice.subscription and invoice.subscription.related_type == "RentalAgreement":
                rental_agreement_id = invoice.subscription.related_id
            elif invoice.metadata and "rental_agreement" in invoice.metadata:
                rental_agreement_id = invoice.metadata.get("rental_agreement")
            elif invoice.subscription and invoice.subscription.metadata and "rental_agreement" in invoice.subscription.metadata:
                rental_agreement_id = invoice.subscription.metadata.get("rental_agreement")
            else:
                rental_agreement_id = None

            log.debug(f"CELERY::: Rental Agreement ID: {rental_agreement_id}")
            if rental_agreement_id:
                rental_agreement = RentalAgreement.get(rental_agreement_id)
                log.debug(f"CELERY::: Rental Agreement: {rental_agreement}")
                if invoice.related_id != rental_agreement_id:
                    invoice.related_type = "RentalAgreement"
                    invoice.related_id = rental_agreement.id
                    invoice.save()

                # Make sure a Rental Invoice exists
                existing = RentalInvoice.get(invoice.stripe_id)
                log.debug(f"CELERY::: Existing Rental Invoice: {existing}")

                if not existing:
                    log.info(f"CELERY::: Creating RentalInvoice from StripeInvoice")
                    # Period start and end are required to track invoice in HangarHub model
                    if invoice.period_start and invoice.period_end:
                        # Create a RentalInvoice
                        existing = RentalInvoice.objects.create(
                            agreement=rental_agreement,
                            stripe_invoice=invoice,
                            stripe_subscription=invoice.subscription,
                            period_start_date=invoice.period_start,
                            period_end_date=invoice.period_end,
                            amount_charged=invoice.amount_charged,
                            status_code="I",  # sync() will map to the correct status code
                        )

                    else:
                        log.info(f"CELERY::: MISSING PERIOD START/END")

                log.debug(f"CELERY::: Rental Invoice: {existing}")

                # Make sure stripe invoice is linked to rental invoice
                if existing and not existing.stripe_invoice:
                    log.debug(f"CELERY::: Linking Stripe invoice to Rental invoice")
                    existing.stripe_invoice = existing
                    existing.save()
                existing.sync()


            else:
                # ToDo: Maybe a HangarHub subscription?
                return False


            if event.event_type == "invoice.created":
                # ToDo: Send an email?
                pass

            return True

        elif invoice and invoice.deleted:
            # No action needed?
            return True

        else:  # No invoice record
            return False
    except Exception as ee:
        Error.record(ee, event)
        return False


def handle_subscription_event(event):
    has_relation = False
    change_handled = False
    try:
        subscription = StripeSubscription.from_stripe_id(event.object_id, event.account_id)
        if subscription and not subscription.deleted:
            if has_relation:
                pass

            elif subscription.related_type and subscription.related_id:
                has_relation = True

            elif subscription.metadata and "rental_agreement" in subscription.metadata:
                subscription.related_type = "RentalAgreement"
                subscription.related_id = subscription.metadata.get("rental_agreement")
                subscription.save()
                has_relation = True

            else:
                # If not linked to a rental agreement, might be a HangarHub subscription
                try:
                    airport = Airport.objects.get(stripe_customer=subscription.customer)
                    if airport:
                        subscription.related_type = "Airport"
                        subscription.related_id = airport.id
                        subscription.save()
                        has_relation = True
                except Airport.DoesNotExist:
                    pass
                except Exception as ee:
                    Error.record(ee, subscription)

            # Can only react to the change if there is a related object
            if has_relation:
                if subscription.related_type == "RentalAgreement":
                    rental_agreement = RentalAgreement.get(subscription.related_id)
                    if not rental_agreement:
                        Error.record(
                            f"{subscription} Relation Invalid: {subscription.related_type} #{subscription.related_id} does not exist"
                        )
                        subscription.related_type = None
                        subscription.related_id = None
                        subscription.save()
                        return False
                    cu_sub = rental_agreement.stripe_subscription
                    fu_sub = rental_agreement.future_stripe_subscription
                    this_sub = subscription
                    if not cu_sub:
                        rental_agreement.stripe_subscription = this_sub
                    elif cu_sub.id == this_sub.id:
                        pass
                    elif this_sub.is_active and not cu_sub.is_active:
                        rental_agreement.stripe_subscription = this_sub
                    elif this_sub.is_active and not fu_sub:
                        rental_agreement.future_stripe_subscription = this_sub
                    elif this_sub.is_active and not fu_sub.is_active:
                        rental_agreement.future_stripe_subscription = this_sub
                    else:
                        Error.record(f"Unsure how to handle subscription event: {event}")
                        return False
                    rental_agreement.save()

                    if this_sub.status in ["past_due", "unpaid"]:
                        # ToDo: Notify AirportManager of "past_due", "unpaid" subscription updates
                        return False

                    # Otherwise, I don't think there's anything else to do atthis time
                    return True

        elif subscription and subscription.deleted:
            return True
        else:
            log.error(f"Unknown subscription: {subscription}")
    except Exception as ee:
        Error.record(ee, event)
    return False


def handle_checkout_session_event(event):
    # Would result in a new subscription, so probably nothing needed???
    return True


def handle_invoice_payment_event(event):
    # Get the invoice data
    try:
        set_stripe_api_key()
        if event.account_id:
            in_pay = stripe.InvoicePayment.retrieve(event.object_id, stripe_account=event.account_id)
        else:
            in_pay = stripe.InvoicePayment.retrieve(event.object_id)
        invoice_stripe_id = in_pay.invoice
        invoice = StripeInvoice.from_stripe_id(invoice_stripe_id, event.account_id)
        invoice.sync()
        # ToDo: Send an email???
        return True
    except Exception as ee:
        Error.record(ee, event)

