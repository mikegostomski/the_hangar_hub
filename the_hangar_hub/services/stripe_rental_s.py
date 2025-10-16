from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service, utility_service, date_service
from base_stripe.services.config_service import set_stripe_api_key
from base_stripe.services import invoice_service
from base_stripe.models.payment_models import StripeSubscription
from base_stripe.models.payment_models import StripeCustomer
from base_stripe.models.payment_models import StripeInvoice as StripeInvoice
from datetime import datetime, timezone, timedelta
from the_hangar_hub.models.rental_models import RentalAgreement, RentalInvoice

log = Log()
env = EnvHelper()


def sync_rental_agreement_invoices(rental_agreement):
    """
    Sync RentalInvoice with base_stripe.StripeInvoice for given RentalAgreement
        - This only looks at a couple of invoices, and runs quickly
    """
    log.trace([rental_agreement])
    customer = rental_agreement.customer
    if not customer:
        # If no customer record, tenant has nothing in Stripe to sync with
        return

    # For all known rental invoices, refresh the data
    for rental_invoice in rental_agreement.relevant_invoice_models():
        if rental_invoice.status_code in ("P", "W", "X"):
            # Invoices that have been paid, waived, or cancelled do not change
            continue
        rental_invoice.sync()

    # Stripe webhooks catch new invoices, but as a backup, check for missed invoices once per session
    if not env.get_session_variable(f"found_invoices_for_{rental_agreement.id}"):
        invoice_service.find_invoices(customer, 5)
        env.set_session_variable(f"found_invoices_for_{rental_agreement.id}", True)

    # Look for new StripeInvoices and create RentalInvoices from them
    for invoice in StripeInvoice.objects.filter(
        customer=customer,
        related_id__isnull=True,
    ):
        existing = RentalInvoice.get(invoice.stripe_id)
        if existing:
            log.info(f"Linking StripeInvoice to existing RentalInvoice: {existing.id}")
            existing.related_type = "RentalInvoice"
            existing.related_id = existing.id
            existing.save()
        else:
            log.info(f"Linking StripeInvoice to new RentalInvoice")
            # Period start and end are required to track invoice in HangarHub model
            if invoice.period_start and invoice.period_end:
                # Create a RentalInvoice
                ri = RentalInvoice.objects.create(
                    agreement=rental_agreement,
                    stripe_invoice=invoice,
                    stripe_subscription=invoice.subscription,
                    period_start_date=invoice.period_start,
                    period_end_date=invoice.period_end,
                    amount_charged=invoice.amount_charged,
                    status_code="I", # sync() will map to the correct status code
                )
                ri.sync()
            else:
                log.error(f"Cannot create RentalInvoice without period start and end dates [{invoice.stripe_id}]")


def sync_rental_agreement_subscriptions(rental_agreement):
    """
    Sync RentalInvoice with base_stripe.StripeSubscription for given RentalAgreement
    """
    log.trace(rental_agreement)
    if rental_agreement.stripe_subscription:
        rental_agreement.stripe_subscription.sync()

    # Look for other active subscriptions
    must_save = False
    customer_id = rental_agreement.stripe_customer_id
    for sub in StripeSubscription.objects.filter(
        status__in=["trialing", "active", "past_due", "unpaid", "paused"],  # Active subscriptions (indexed)
        customer__stripe_id=customer_id,                                    # For this customer (indexed)
        metadata__RentalAgreement=rental_agreement.id         # For this RentalAgreement
    ):
        if sub.stripe_id == rental_agreement.stripe_subscription_id:
            continue
        elif sub.status == "trialing":
            if rental_agreement.active_subscription:
                rental_agreement.future_stripe_subscription = sub
            else:
                rental_agreement.stripe_subscription = sub
            must_save = True
        elif not rental_agreement.active_subscription:
            rental_agreement.stripe_subscription = sub
            must_save = True
        elif rental_agreement.stripe_subscription_status != "active" and sub.status == "active":
            rental_agreement.stripe_subscription = sub
            must_save = True
        else:
            rental_agreement.future_stripe_subscription = sub
            must_save = True

        if rental_agreement.stripe_subscription == rental_agreement.future_stripe_subscription:
            rental_agreement.future_stripe_subscription = None
            must_save = True

    if must_save:
        rental_agreement.save()


def sync_airport_invoices(airport):
    """
    Sync RentalInvoice with base_stripe.StripeInvoice for all RentalAgreements at given Airport
        - This may look at a lot of invoices. Perhaps best done asynchronously?
    """
    for rental_agreement in RentalAgreement.objects.filter(airport=airport):
        sync_rental_agreement_invoices(rental_agreement)








