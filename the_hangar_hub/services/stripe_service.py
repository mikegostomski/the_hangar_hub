from django.http import HttpResponseForbidden

from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.services import product_service
from base_stripe.models.connected_account import StripeConnectedAccount
from base_stripe.models.payment_models import StripeSubscription
from base_stripe.models.payment_models import StripeCustomer
from datetime import datetime, timezone, timedelta
from base.models import Variable

log = Log()
env = EnvHelper()


def get_subscription_prices():
    return {price.lookup_key: price for  price in product_service.get_price_list() if price.name == "The Hangar Hub"}



def get_customer_from_airport(airport):
    log.trace()

    if not airport.stripe_customer:
        return None
    # ToDo: Just use the Customer model(?)
    return airport.stripe_customer.api_data()

def modify_customer_from_airport(airport):
    log.trace()

    if not airport.stripe_customer:
        return None

    try:
        set_stripe_api_key()
        customer = stripe.Customer.modify(
            airport.stripe_customer.stripe_id,
            name=airport.display_name,
            email=airport.billing_email,
            phone=airport.billing_phone,
            address=get_stripe_address_dict(
                airport.billing_street_1,
                airport.billing_street_2,
                airport.billing_city,
                airport.billing_state,
                airport.billing_zip,
                airport.country
            ),
            # No account needed
        )
        return customer

    except Exception as ee:
        Error.record(ee, airport)
    return False









def get_session_details(session_id):
    try:
        set_stripe_api_key()
        return stripe.checkout.Session.retrieve(session_id)
    except Exception as ee:
        Error.unexpected(
            "Unable to retrieve checkout session status", ee, session_id
        )
        return None

def get_airport_subscriptions(airport):
    if airport and airport.stripe_customer:
        try:
            set_stripe_api_key()
            return stripe.Subscription.list(
                customer=airport.stripe_customer.stripe_id,
                expand=['data.latest_invoice.subscription_details']
            )
        except Exception as ee:
            Error.record(
                ee, f"get_airport_subscriptions({airport})"
            )
    return None


def get_customer_portal_session(airport):
    if airport and airport.stripe_customer:
        try:
            set_stripe_api_key()
            session = stripe.billing_portal.Session.create(
                customer=airport.stripe_customer.stripe_id,
                return_url=f"{env.absolute_root_url}{reverse('airport:manage', args=[airport.identifier])}",
            )
            if session and hasattr(session, "url"):
                return session.url
        except Exception as ee:
            Error.record(
                ee, f"get_customer_portal_session({airport})"
            )
    return None