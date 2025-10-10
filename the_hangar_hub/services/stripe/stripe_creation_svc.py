"""
Any objects created in Stripe directly by HangarHub code should live here
"""

from base.models.utility.error import EnvHelper, Log, Error
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.models.payment_models import StripeCheckoutSession, StripeSubscription, StripeCustomer, StripeInvoice
from base.models.utility.variable import Variable
from base_stripe.services import accounts_service
from base.services import message_service, utility_service
from datetime import datetime, timezone, timedelta
from django.urls import reverse
import stripe
from decimal import Decimal
from the_hangar_hub.services.stripe import stripe_lookup_svc

log = Log()
env = EnvHelper()


def create_customer_from_airport(airport):
    log.trace([airport])

    if airport.stripe_customer:
        return True  # Already has customer, so consider a success

    customer_model = StripeCustomer.get_or_create(
        full_name=airport.display_name,
        email=airport.billing_email,
        phone=airport.billing_phone,
        address_dict=get_stripe_address_dict(
            airport.billing_street_1,
            airport.billing_street_2,
            airport.billing_city,
            airport.billing_state,
            airport.billing_zip,
            airport.country
        ),
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
        connected_account = accounts_service.create_account(params_dict)
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
        set_stripe_api_key()
        checkout_session = stripe.checkout.Session.create(
            customer_email=application.email,
            mode="payment",
            line_items=[
                {
                    'price_data': {
                        "unit_amount": airport.application_fee_stripe,
                        # "product": "prod_Slrtn5xjteLKes",
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
            stripe_account= airport.stripe_account.stripe_id,
            # application_fee_amount=airport.application_fee_stripe * .01,  # 1% fee for HangarHub
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


def get_subscription_checkout_session(rental_agreement, collection_start_date, expiration_date=None):
    try:
        # Gather data
        tenant = rental_agreement.tenant
        airport = rental_agreement.airport

        # Get customer's Stripe ID (required)
        customer = stripe_lookup_svc.get_stripe_customer(tenant)
        if not customer:
            message_service.post_error("Unable to obtain Stripe customer ID for tenant.")
            return False

        # Look for existing subscriptions
        existing = StripeSubscription.objects.filter(
            customer=customer,
            status__in=StripeSubscription.active_statuses(),
            metadata__RentalAgreement=rental_agreement.id,
        )
        if existing:
            message_service.post_error("Tenant already has an active subscription.")
            return False
    except Exception as ee:
        Error.unexpected("There was an error gathering subscription data from the rental agreement", ee)
        return False

    # Process subscription start date
    trial_days = None
    try:
        now = datetime.now(timezone.utc)
        nowish = now + timedelta(minutes=2) # Anchor dates must be in the future. 2 minutes is enough.
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if not collection_start_date:
            collection_start_date = rental_agreement.start_date

        # If collection started in the past
        if collection_start_date < today:
            backdate_start_date = int(collection_start_date.timestamp())
            billing_cycle_anchor = _next_anchor_date(now, collection_start_date.day)
            billing_cycle_anchor_config = None

        # If collection started today, but before now
        elif collection_start_date < nowish:
            # Set anchor to two minutes in the future
            anchor_time = nowish
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
                trial_days = (collection_start_date - today).days
                if trial_days == 0:
                    trial_days = None  # Stripe will not allow 0
    except Exception as ee:
        Error.unexpected("Unable to process subscription start date", ee, collection_start_date)
        return False

    try:
        amount_due = int(rental_agreement.rent * 100)  # In cents
        currency = "usd"
        application_fee_percent = utility_service.convert_to_decimal(airport.stripe_tx_fee * 100)
        return_url = reverse('rent:rental_agreement_router', args=[airport.identifier, rental_agreement.id])

        # Expiration date may be specified by airport in local time
        if expiration_date:
            expiration_date = expiration_date.astimezone(timezone.utc)
            expires_at = int(expiration_date.timestamp())
            log.warning("Expiration date not used. Will expire in 24 hours.")

        set_stripe_api_key()
        checkout_session = stripe.checkout.Session.create(
            customer=customer.stripe_id,
            line_items=[{
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
            mode='subscription',
            subscription_data={
                "trial_period_days": trial_days,
                "metadata": {
                    "airport": airport.identifier,
                    "rental_agreement": rental_agreement.id,
                    "hangar": rental_agreement.hangar.code,
                },
                "invoice_settings": {
                    "issuer": {"type": "account", "account": airport.stripe_account.stripe_id},
                    # "metadata": {
                    #     "airport": airport.identifier,
                    #     "rental_agreement": rental_agreement.id,
                    #     "hangar": rental_agreement.hangar.code,
                    # }
                },
                "on_behalf_of": airport.stripe_account.stripe_id,
                "transfer_data": {"destination": airport.stripe_account.stripe_id},
                "application_fee_percent": application_fee_percent,
            },
            metadata={
                "rental_agreement": rental_agreement.id
            },
            # expires_at=expires_at,
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


def stripe_invoice_from_rental_invoice(rental_invoice):
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
        if tenant.stripe_customer_id:
            stripe_customer = StripeCustomer.get(tenant.stripe_customer_id)
        else:
            stripe_customer = StripeCustomer.get_or_create(tenant.display_name, tenant.email, tenant.user)
            tenant.customer = stripe_customer
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
                "rental_agreement": rental_agreement.id,
                "hangar": hangar.code,
                "type": "manual"
            },
            "application_fee_amount": tx_fee,
            "issuer": {"type": "account", "account": airport.stripe_account.stripe_id},
            "on_behalf_of": airport.stripe_account.stripe_id,
            "transfer_data": {"destination": airport.stripe_account.stripe_id},
            "due_date": rental_invoice.stripe_due_date(),
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
            return int(from_date.replace(month=from_date.month + 1, day=anchor_day_number).timestamp())
    else:
        return int(from_date.timestamp())