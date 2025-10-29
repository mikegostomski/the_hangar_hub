"""
Any objects created in Stripe directly by HangarHub code should live here
"""
from base.classes.util.date_helper import DateHelper
from base.models.utility.error import EnvHelper, Log, Error
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.models.payment_models import StripeCheckoutSession, StripeSubscription, StripeCustomer, StripeInvoice
from base_stripe.models.product_models import StripeProduct
from base_stripe.models.connected_account import StripeConnectedAccount
from the_hangar_hub.models.airport_customer import AirportCustomer
from base.models.utility.variable import Variable
from base.services import message_service, utility_service
from datetime import datetime, timezone, timedelta
from django.urls import reverse
import stripe
from decimal import Decimal
from the_hangar_hub.services.stripe import stripe_lookup_svc
from the_hangar_hub.classes.checkout_session_helper import StripeCheckoutSessionHelper
import random

log = Log()
env = EnvHelper()


def create_customer_from_airport(airport):
    log.trace([airport])

    if airport.stripe_customer:
        return True  # Already has customer, so consider a success

    customer_model = StripeCustomer.obtain(
        display_name=airport.display_name,
        email=airport.billing_email,
        # No account needed (Account == Hangar Hub)
    )

    try:
        if customer_model:
            airport.stripe_customer = customer_model
            airport.save()
            log.info(f"{airport} is now Stripe customer: {customer_model.stripe_id}")
            return True
        else:
            message_service.post_error("Unable to create customer record in payment portal.")
    except Exception as ee:
        Error.unexpected(
            "Unable to create customer record in payment portal", ee
        )
    return False


def hh_checkout_session(airport, price):
    """
    Create a checkout session for a HangarHub subscription
    """
    log.trace([airport, price])

    # ToDo: Previous subscribers do not get another free trial
    trial_days = price.trial_days

    try:
        set_stripe_api_key()
        checkout_session = stripe.checkout.Session.create(
            customer=airport.stripe_customer.stripe_id,
            line_items=[
                {
                    'price': price.stripe_id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            subscription_data={
                "trial_period_days": trial_days,
            },
            metadata={
                "airport": airport.identifier,
                "type": "HangarHub",
            },
            success_url=f"{env.absolute_root_url}{reverse('airport:subscription_success', args=[airport.identifier])}",
            cancel_url=f"{env.absolute_root_url}{reverse('airport:subscription_failure', args=[airport.identifier])}",
        )
        co_session_id = checkout_session.id
        co_model = StripeCheckoutSession.from_stripe_id(co_session_id, stripe_data=checkout_session)
        co_model.related_type = "Airport"
        co_model.related_id = airport.id
        co_model.save()
        return co_model
    except Exception as ee:
        Error.unexpected("Unable to create a payment session", ee)
        return None


def create_connected_account(airport):
    """
    Create connected account for Airport in Stripe
    """
    log.trace([airport])

    if airport.stripe_account:
        # Already exists... return it
        return airport.stripe_account

    try:
        # Stripe uses two-digit country codes. Airport list was populated with three.
        if len(airport.country) == 3:
            # This works for the USA and CAN. Future airports should import the 2-digit code
            airport.country = airport.country[:2]
            airport.save()

        params_dict = {
            "metadata": {"airport": airport.identifier},
            "country": airport.country,
            "email": airport.billing_email,
            "capabilities": {
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            "controller": {
                "fees": {"payer": "account"},
                "stripe_dashboard": {"type": "full"},
            },
            "tos_acceptance": {"service_agreement": "full"},
            "business_type": "company",
            "business_profile": {
                "mcc": "4582",  # Code for airports
                "name": airport.display_name,
                "support_email": airport.billing_email,
                "support_phone": airport.billing_phone,
                "url": airport.url,
                "product_description": "Airport Payment",
            },
            "company": {
                "name": airport.display_name,
                "phone": airport.billing_phone,
                "address": get_stripe_address_dict(
                    airport.billing_street_1,
                    airport.billing_street_2,
                    airport.billing_city,
                    airport.billing_state,
                    airport.billing_zip,
                    airport.country,
                ),
            }
        }
        connected_account = StripeConnectedAccount.create(**params_dict)
        if connected_account:
            airport.stripe_account = connected_account
            airport.save()
        return connected_account
    except Exception as ee:
        Error.record(ee, airport)
        return False


def get_checkout_session_application_fee(application):
    """
    Get checkout session for hangar applicant when airport charges an application fee
    """
    try:
        airport = application.airport

        # Get or create a Stripe customer for this Application Fee
        airport_customer = AirportCustomer.get(airport, application)
        stripe_customer = airport_customer.stripe_customer if airport_customer else None
        stripe_customer_id = stripe_customer.stripe_id if stripe_customer else None
        log.debug(f"Stripe Customer: {stripe_customer_id}")

        set_stripe_api_key()
        checkout_session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            mode="payment",
            line_items=[
                {
                    'price_data': {
                        "unit_amount": airport.application_fee_stripe,
                        "product_data": {"name": "Application Fee", "description": f"Hangar application at {airport.identifier}"},
                        "currency": "usd",
                    },
                    'quantity': 1,
                },
            ],
            metadata={
                "airport": airport.identifier,
                "type": "ApplicationFee",
                "Application": application.id,
                "User": application.user.id,
            },
            success_url=f"{env.absolute_root_url}{reverse('application:record_payment', args=[application.id])}",
            cancel_url=f"{env.absolute_root_url}{reverse('application:record_payment', args=[application.id])}",
            # stripe_account= airport.stripe_account.stripe_id,
            # application_fee_amount=airport.application_fee_stripe * airport.stripe_tx_fee,
            payment_intent_data={
                # "setup_future_usage": "off_session",
                "application_fee_amount": int(airport.application_fee_stripe * airport.stripe_tx_fee),
            },
            stripe_account=airport.stripe_account.stripe_id,
        )
        co_session_id = checkout_session.id
        co_model = StripeCheckoutSession.from_stripe_id(co_session_id, stripe_data=checkout_session)
        co_model.related_type = "Application"
        co_model.related_id = application.id
        co_model.save()
        return checkout_session
    except Exception as ee:
        Error.unexpected(
            "Unable to create a payment session", ee
        )
        return None


def get_subscription_checkout_session(rental_agreement, collection_start_date):
    try:
        # Get hangar rent product for this airport
        product = StripeProduct.obtain("Hangar Rent", rental_agreement.airport.stripe_account)
        if not product:
            message_service.post_error("Unable to obtain Stripe product for Hangar Rent.")
            return False

        # Gather data
        tenant = rental_agreement.tenant
        airport = rental_agreement.airport

        # Get or create a Stripe customer for this Application Fee
        airport_customer = AirportCustomer.get(airport, tenant.contact)
        stripe_customer = airport_customer.stripe_customer if airport_customer else None
        stripe_customer_id = stripe_customer.stripe_id if stripe_customer else None
        log.debug(f"Stripe Customer: {stripe_customer_id}")
        if not stripe_customer_id:
            message_service.post_error("Unable to obtain Stripe customer ID for tenant.")
            return False

        # If customer id does not match existing rental agreement customer, update it
        if rental_agreement.customer and rental_agreement.customer.stripe_id != stripe_customer_id:
            rental_agreement.customer = stripe_customer
            rental_agreement.save()

        # Look for existing subscriptions
        existing = StripeSubscription.objects.filter(
            customer=stripe_customer,
            status__in=StripeSubscription.active_statuses(),
            metadata__RentalAgreement=rental_agreement.id,
        )
        if existing:
            # ToDo: If price increases, is that a new subscription, or is this one altered?
            message_service.post_error("Tenant already has an active subscription.")
            return False
    except Exception as ee:
        Error.unexpected("There was an error gathering subscription data from the rental agreement", ee)
        return False

    try:
        now = datetime.now(timezone.utc)

        # By default, start with the rental agreement start date
        if not collection_start_date:
            collection_start_date = rental_agreement.start_date
        else:
            # Make sure specified date is UTC
            collection_start_date = collection_start_date.astimezone(timezone.utc)

        # Is the start date on the current day (local time)
        local_today = now.astimezone(airport.tz).replace(hour=0, minute=0, second=0, microsecond=0)
        local_start = collection_start_date.astimezone(airport.tz).replace(hour=0, minute=0, second=0, microsecond=0)
        is_today = local_start == local_today

        trial_days = None
        backdate_start_date = billing_cycle_anchor = backdate_days = proration_behavior = None
        if is_today:
            billing_cycle_anchor = None

        elif collection_start_date < now:
            # Checkout sessions cannot be backdated
            # Subscriptions can be created in the past, but only if the tenant already had a saved payment method
            # There is no way to start a subscription in the past unless the tenant already set up their payment method

            # Save the desired start date in the metadata.
            # A manual invoice could be created to pay the past-due amount after the tenant has a payment method.

            # Start the subscription now
            billing_cycle_anchor = None

            # Calculate the anchor for the past date and pass it via metadata
            # Store the backdated start in metadata for webhook processing
            backdate_start_date = int(collection_start_date.timestamp())
            backdate_days = int((now - collection_start_date).days)

        else:
            # collection_start_date is after today (local time).
            # select a reasonable time on that day to start billing.
            # Infuse some randomness in the time selection to avoid everyone's billing happening at the same time
            local_start_time = collection_start_date.astimezone(airport.tz)
            start_hour = random.choice(range(8, 12))   # 8am - noon
            start_minute = random.choice(range(0, 59)) # any minute
            local_start_time = local_start_time.replace(hour=start_hour, minute=start_minute)
            billing_cycle_anchor = int(local_start_time.timestamp())
            proration_behavior = "none"

            # Collection starts in the future: use trial period to delay billing
            # billing_cycle_anchor = None
            # trial_days = (collection_start_date - now).days
            # # If billing starts tomorrow, it may be just a few hours and result in 0 days
            # if trial_days < 1:
            #     trial_days = 1
            #
            # if trial_days == 0:
            #     trial_days = None  # Stripe won't allow 0 days

        cd_s = DateHelper(collection_start_date)
        cd_n = DateHelper(now)
        log.debug(f"""
        Start Collecting: {cd_s.banner_date_time()}
        Now: {cd_n.banner_date_time()}
        Trial Days: {trial_days}
        """)

    except Exception as ee:
        Error.unexpected("Unable to process subscription start date", ee, collection_start_date)
        return False

    try:
        amount_due = int(rental_agreement.rent * 100)  # In cents
        currency = "usd"
        application_fee_percent = utility_service.convert_to_decimal(airport.stripe_tx_fee * 100)
        application_fee_amount = int(rental_agreement.rent * airport.stripe_tx_fee * 100)
        return_url = reverse('rent:rental_agreement_router', args=[airport.identifier, rental_agreement.id])

        set_stripe_api_key()

        # Build subscription data
        subscription_data = {
            "metadata": {
                "airport": airport.identifier,
                "rental_agreement": rental_agreement.id,
                "hangar": rental_agreement.hangar.code,
                "backdate_start_date": str(backdate_start_date),
                "backdate_days": str(backdate_days),
            },
            "invoice_settings": {
                "issuer": {"type": "account", "account": airport.stripe_account.stripe_id},
            },
            # "on_behalf_of": airport.stripe_account.stripe_id,
            # "transfer_data": {"destination": airport.stripe_account.stripe_id},
            "application_fee_percent": application_fee_percent,
            "stripe_account": airport.stripe_account.stripe_id,
        }

        # Add trial days if applicable
        if trial_days is not None:
            subscription_data["trial_period_days"] = trial_days

        # Add billing cycle anchor if set
        if billing_cycle_anchor is not None:
            subscription_data["billing_cycle_anchor"] = billing_cycle_anchor

        # Add proration_behavior if set
        if proration_behavior is not None:
            subscription_data["proration_behavior"] = proration_behavior

        # Metadata for CheckoutSession
        metadata = {
            "rental_agreement": rental_agreement.id,
        }
        if backdate_start_date:
            metadata["backdate_start_date"] = str(backdate_start_date)
            metadata["backdate_days"] = str(backdate_days)

        checkout_session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            line_items=[{
                "price_data": {
                    "unit_amount": amount_due,
                    "product": product.stripe_id,
                    "currency": currency,
                    "recurring": {
                        "interval": "month",
                    }
                },
                "quantity": 1,
            }],
            mode='subscription',
            subscription_data=subscription_data,
            metadata=metadata,
            payment_intent_data={
                "setup_future_usage": "off_session",
                "application_fee_amount": application_fee_amount,
            },
            stripe_account=airport.stripe_account.stripe_id,
            success_url=f"{env.absolute_root_url}{return_url}",
            cancel_url=f"{env.absolute_root_url}{return_url}",
        )

        co_session_id = checkout_session.id
        log.debug(f"CHECKOUT SESSION ID: {co_session_id}")

        # Save model to track this CO Session
        co_model = StripeCheckoutSession.from_stripe_id(co_session_id, stripe_data=checkout_session)
        co_model.related_type = "RentalAgreement"
        co_model.related_id = rental_agreement.id
        co_model.save()

        return co_model

    except Exception as ee:
        Error.unexpected("Unable to create rental subscription", ee, rental_agreement)
        return False


def stripe_invoice_from_rental_invoice(rental_invoice, send_invoice=False):
    """
    Given a RentalInvoice, generate an invoice in Stripe and create a base_stripe.StripeInvoice
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
        if rental_agreement.stripe_customer_id:
            stripe_customer = StripeCustomer.get(rental_agreement.stripe_customer_id)
        else:
            stripe_customer = StripeCustomer.obtain(
                display_name=tenant.display_name, email=tenant.email, user=tenant.user, account=airport.stripe_account
            )
            rental_agreement.customer = stripe_customer
            rental_agreement.save()
        if not stripe_customer:
            message_service.post_error("Unable to obtain Stripe customer ID for tenant.")
            return False

        # Determine invoice amount and tx fee (in cents, as expected by Stripe)
        invoice_amount = int((Decimal(rental_invoice.amount_charged) - Decimal(rental_invoice.amount_paid)) * 100)
        tx_fee = int(invoice_amount * airport.stripe_tx_fee)

        if send_invoice:
            collection_method = "send_invoice"
            due_date = rental_invoice.stripe_due_date()
        else:
            collection_method = "charge_automatically"
            due_date = None

        # Convert into a Stripe invoice (one-time)
        parameters = {
            "auto_advance": True,
            "collection_method": collection_method,
            "customer": stripe_customer.stripe_id,
            "description": f"Manual Invoice for Hangar {hangar.code}",
            "metadata": {
                "airport": airport.identifier,
                "rental_agreement": rental_agreement.id,
                "hangar": hangar.code,
                "type": "manual"
            },
            "application_fee_amount": tx_fee,
            "stripe_account": airport.stripe_account.stripe_id,
            "issuer": {"type": "account", "account": airport.stripe_account.stripe_id},
            # "on_behalf_of": airport.stripe_account.stripe_id,
            # "transfer_data": {"destination": airport.stripe_account.stripe_id},
            "due_date": due_date,
        }
        set_stripe_api_key()
        invoice_data = stripe.Invoice.create(**parameters)
        invoice_id = invoice_data.get("id")
        # Create line item...
        stripe.Invoice.add_lines(
            invoice_id,
            lines=[
                {"description": f"Hangar {hangar.code}", "amount": invoice_amount},
            ]
        )

        stripe_invoice = StripeInvoice.from_stripe_id(invoice_id)
        stripe_invoice.related_type = "RentalAgreement"
        stripe_invoice.related_id = rental_agreement.id
        stripe_invoice.save()
        rental_invoice.stripe_invoice = stripe_invoice
        rental_invoice.save()

        message_service.post_success("Stripe invoice was created.")
        return True

    except Exception as ee:
        Error.unexpected("Unable to create Stripe invoice", ee, rental_invoice)
        return None






def _next_anchor_date(from_date, anchor_day_number):
    """
    Given a datetime, get the next billing anchor date (could be same date)
    (essentially gets the same day next month, or uses the given date)
    """
    from_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
    if int(from_date.day) < anchor_day_number:
        return int(from_date.replace(day=anchor_day_number).timestamp())
    elif int(from_date.day) > anchor_day_number:
        if from_date.month == 12:
            return int(from_date.replace(month=1, day=anchor_day_number, year=from_date.year + 1).timestamp())
        else:
            return from_date.replace(month=from_date.month + 1, day=anchor_day_number)
    else:
        return int(from_date.timestamp())