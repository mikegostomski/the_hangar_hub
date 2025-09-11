from django.http import HttpResponseForbidden

from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service, utility_service, date_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.services import price_service, accounts_service, invoice_service
from base_stripe.models.connected_account import ConnectedAccount
from base_stripe.models.payment_models import Subscription
from base_stripe.models.payment_models import Customer
from base_stripe.models.payment_models import Invoice as StripeInvoice
from datetime import datetime, timezone, timedelta
from the_hangar_hub.models.rental_models import RentalAgreement

log = Log()
env = EnvHelper()


def sync_rental_agreement_invoices(rental_agreement):
    """
    Sync RentalInvoice with base_stripe.Invoice for given RentalAgreement
        - This only looks at a couple of invoices, and runs quickly
    """
    for rental_invoice in rental_agreement.relevant_invoice_models():
        if rental_invoice.status_code in ("P", "W", "X"):
            # Invoices that have been paid, waived, or cancelled do not change
            continue
        rental_invoice.sync()


def sync_rental_agreement_subscriptions(rental_agreement):
    """
    Sync RentalInvoice with base_stripe.Subscription for given RentalAgreement
    """
    log.trace(rental_agreement)
    if rental_agreement.stripe_subscription:
        rental_agreement.stripe_subscription.sync()

    # Look for other active subscriptions
    must_save = False
    customer_id = rental_agreement.tenant.stripe_customer_id
    required_metadata = f'"rental_agreement": "{rental_agreement.id}"'
    for sub in Subscription.objects.filter(
        status__in=["trialing", "active", "past_due", "unpaid", "paused"],  # Active subscriptions (indexed)
        customer__stripe_id=customer_id,                                    # For this customer (indexed)
        metadata__contains=required_metadata                                # For this RentalAgreement
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
    Sync RentalInvoice with base_stripe.Invoice for all RentalAgreements at given Airport
        - This may look at a lot of invoices. Perhaps best done asynchronously?
    """
    for rental_agreement in RentalAgreement.objects.filter(airport=airport):
        sync_rental_agreement_invoices(rental_agreement)


def stripe_invoice_from_rental_invoice(rental_invoice):
    """
    Given a RentalInvoice, generate an invoice in Stripe and create a base_stripe.Invoice
    """
    if not rental_invoice:
        return False

    if rental_invoice.stripe_invoice:
        message_service.post_warning("The specified invoice has already been created in Stripe")
        return False

    try:
        # Gather data
        rental_agreement = rental_invoice.agreement
        tenant = rental_agreement.tenant
        hangar = rental_agreement.hangar
        airport = rental_agreement.airport

        # Get customer's Stripe ID (required)
        if tenant.stripe_customer_id:
            stripe_customer = Customer.get(tenant.stripe_customer_id)
        else:
            stripe_customer = Customer.get_or_create(tenant.display_name, tenant.email, tenant.user)
            tenant.stripe_customer_id = stripe_customer.stripe_id
            tenant.save()
        if not stripe_customer:
            message_service.post_error("Unable to obtain Stripe customer ID for tenant.")
            return False

        # Determine invoice amount and tx fee (in cents, as expected by Stripe)
        invoice_amount = int((Decimal(rental_invoice.amount_charged) - Decimal(rental_invoice.amount_paid)) * 100)
        tx_fee = int(invoice_amount * airport.stripe_tx_fee)

        # Convert into a Stripe invoice (one-time)
        parameters = {
            "auto_advance": True,
            "collection_method": "send_invoice",  # "charge_automatically"
            "customer": stripe_customer.stripe_id,
            "description": f"Manual Invoice for Hangar {hangar.code}",
            "metadata": {
                "airport": airport.identifier,
                "agreement": rental_agreement.id, "hangar": hangar.code
            },
            "application_fee_amount": tx_fee,
            "issuer": {"type": "account", "account": airport.stripe_account_id},
            "on_behalf_of": airport.stripe_account_id,
            "transfer_data": {"destination": airport.stripe_account_id},
            "due_date": rental_invoice.stripe_due_date(),
        }
        set_stripe_api_key()
        invoice_data = stripe.Invoice.create(**parameters)
        invoice_id = invoice_data.get("id")
        # Create line item...
        stripe.Invoice.add_lines(
            invoice_id,
            lines=[
                {"description": f"Hanger {hangar.code}", "amount": invoice_amount},
            ]
        )

        stripe_invoice = StripeInvoice.from_stripe_id(invoice_id)
        rental_invoice.stripe_invoice = stripe_invoice
        rental_invoice.save()

        message_service.post_success("Stripe invoice was created.")
        return True

    except Exception as ee:
        Error.unexpected("Unable to create Stripe invoice", ee, rental_invoice)
        return None


def stripe_subscription_from_rental_invoice(rental_invoice):
    """
    Given a RentalInvoice, generate a subscription in Stripe and create a base_stripe.Subscription
    """
    if not rental_invoice:
        return False

    if rental_invoice.stripe_subscription:
        try:
            rental_invoice.stripe_subscription.sync()
            if rental_invoice.stripe_subscription.status in ["trialing", "active", "past_due", "unpaid", "paused"]:
                message_service.post_warning("This rental agreement already has a subscription in Stripe")
                return False
            else:
                # Forget the inactive subscription
                log.warning(f"Removing inactive subscription: {rental_invoice.stripe_subscription.stripe_id}")
                rental_invoice.stripe_subscription = None
                rental_invoice.save()
        except Exception as ee:
            Error.unexpected("Unable to process existing subscription", ee, rental_invoice.stripe_subscription.stripe_id)
            return False

    try:
        # Gather data
        rental_agreement = rental_invoice.agreement
        tenant = rental_agreement.tenant
        hangar = rental_agreement.hangar
        airport = rental_agreement.airport

        # Get customer's Stripe ID (required)
        if tenant.stripe_customer_id:
            stripe_customer = Customer.get(tenant.stripe_customer_id)
        else:
            stripe_customer = Customer.get_or_create(tenant.display_name, tenant.email, tenant.user)
            tenant.stripe_customer_id = stripe_customer.stripe_id
            tenant.save()
        if not stripe_customer:
            message_service.post_error("Unable to obtain Stripe customer ID for tenant.")
            return False

        # If Stripe invoice exists, make sure data is up-to-date
        if rental_invoice.stripe_invoice:
            rental_invoice.stripe_invoice.sync()
            rental_invoice.sync()

        # If there is a draft invoice, cancel it.
        if rental_invoice.stripe_invoice.status == "draft":
            if invoice_service.delete_draft_invoice(rental_invoice.stripe_id):
                rental_invoice.stripe_invoice = None
                if rental_invoice.status_code == "I":
                    rental_invoice.status_code = "O"
                rental_invoice.save()
            else:
                message_service.post_error(
                    "Draft invoice was not canceled. Finalize or delete draft before starting subscription."
                )
                return False

        # Determine start date of subscription
        try:
            current_invoice_start_date = rental_invoice.period_start_date
            next_invoice_start_date = rental_invoice.period_end_date + timedelta(days=1)

            # If stripe invoice was already created, start subscription after the current period
            if rental_invoice.stripe_invoice:
                collection_start_date = next_invoice_start_date
            # If already paid or waived, start subscription after the current period
            elif rental_invoice.status_code in ["P", "W"]:
                collection_start_date = next_invoice_start_date
            # If partial payment recorded, start subscription after the current period
            elif rental_invoice.amount_paid:
                collection_start_date = next_invoice_start_date
            # If current invoice covers more than a month, start after this period
            elif (rental_invoice.period_end_date - rental_invoice.period_start_date).days > 31:
                collection_start_date = next_invoice_start_date
            # Otherwise, create subscription for this period
            else:
                collection_start_date = current_invoice_start_date
        except Exception as ee:
            Error.unexpected("Unable to determine subscription start date", ee)
            return False


        # /////////////////////////////////////////////////////////////////////


        try:
            now = datetime.now(timezone.utc)
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            billing_cycle_anchor_day = trial_end = None

            # If collection started in the past
            if collection_start_date < today:
                backdate_start_date = int(collection_start_date.timestamp())
                billing_cycle_anchor = next_anchor_date(now, collection_start_date.day)
                billing_cycle_anchor_config = None

            # If collection started today, but before now
            elif collection_start_date < now:
                # Set anchor to two minutes in the future
                anchor_time = now + timedelta(minutes=2)
                backdate_start_date = None
                billing_cycle_anchor = int(anchor_time.timestamp())
                billing_cycle_anchor_config = None
            else:
                backdate_start_date = None
                billing_cycle_anchor = int(collection_start_date.timestamp())
                billing_cycle_anchor_config = None


                # If collection does not start until future date, use trial period to prevent billing until then
                now = datetime.now(timezone.utc)
                if collection_start_date > now:
                    trial_end = int(collection_start_date.timestamp())
                else:
                    trial_end = None
        except Exception as ee:
            Error.unexpected("Unable to process collection start date", ee, collection_start_date)
            return False

        try:
            amount_due = int(rental_invoice.amount_charged * 100)  # In cents
            currency = "usd"
            charge_automatically = True
            days_until_due = 7
            application_fee_percent = utility_service.convert_to_decimal(airport.stripe_tx_fee * 100)

            p = {
                    "application_fee_percent": application_fee_percent,
                    "backdate_start_date": backdate_start_date,
                    "billing_cycle_anchor": date_service.string_to_date(billing_cycle_anchor),
                    "trial_end": date_service.string_to_date(trial_end),
                    "billing_cycle_anchor_config": billing_cycle_anchor_config,
                }
            log.debug(f"SubscriptionParameters:\n\n{p}\n")

            set_stripe_api_key()
            subscription = stripe.Subscription.create(
                customer=stripe_customer.stripe_id,
                on_behalf_of=airport.stripe_account_id,
                transfer_data={"destination": airport.stripe_account_id},
                application_fee_percent=application_fee_percent,
                invoice_settings={
                    "issuer": {"type": "account", "account": airport.stripe_account_id}
                },

                description=f"Hanger {hangar.code} at {airport.display_name}",
                items=[{
                    "price_data": {
                        "unit_amount": amount_due,
                        "product": "prod_SlruA5rXT1JeD2", # ToDo: Make a setting? Variable?
                        "currency": currency,
                        "recurring": {
                            "interval": "month",
                        }
                    },
                    "quantity": 1,
                }],

                collection_method="charge_automatically" if charge_automatically else "send_invoice",
                days_until_due=None if charge_automatically else days_until_due,

                billing_cycle_anchor=billing_cycle_anchor,
                billing_cycle_anchor_config=billing_cycle_anchor_config,
                trial_end=trial_end,
                backdate_start_date=backdate_start_date,
                proration_behavior="create_prorations" if collection_start_date > now else None,
                metadata={
                    "rental_agreement": rental_agreement.id, "airport": airport.identifier, "hangar": hangar.code
                }
            )
            subscription_id = subscription.get("id")
            sub_model = Subscription.from_stripe_id(subscription_id)

            if not rental_agreement.stripe_subscription:
                rental_agreement.stripe_subscription = sub_model
            elif sub_model.status == "trialing":
                rental_agreement.future_stripe_subscription = sub_model

            elif not rental_agreement.stripe_subscription.is_active:
                rental_agreement.stripe_subscription = sub_model
            elif rental_agreement.stripe_subscription.status != "active" and sub_model.status == "active":
                rental_agreement.stripe_subscription = sub_model
            else:
                rental_agreement.future_stripe_subscription = sub_model

            return sub_model
        except Exception as ee:
            Error.unexpected("Unable to create rental subscription", ee, rental_invoice)
            return None

    except Exception as ee:
        Error.unexpected("Unable to create Stripe subscription", ee, rental_invoice)
        return None


def next_anchor_date(from_date, anchor_day_number):
    """Given a datetime, get the next billing anchor date (could be same date)"""
    from_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
    if int(from_date.day) < anchor_day_number:
        return int(from_date.replace(day=anchor_day_number).timestamp())
    elif int(from_date.day) > anchor_day_number:
        if from_date.month == 12:
            return int(from_date.replace(month=1, day=anchor_day_number, year=from_date.year + 1).timestamp())
        else:
            return int(from_date.replace(month=from_date.month + 1, day=anchor_day_number).timestamp())
    else:
        return int(from_date.timestamp())




