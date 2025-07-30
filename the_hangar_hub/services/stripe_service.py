from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.services import price_service

log = Log()
env = EnvHelper()


def get_subscription_prices():
    return {price.lookup_key: price for  price in price_service.get_price_list() if price.name == "The Hangar Hub"}


def create_customer_from_airport(airport):
    log.trace()

    if airport.stripe_customer_id:
        return True  # Already has customer ID, so consider a success

    try:
        set_stripe_api_key()
        customer = stripe.Customer.create(
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
        )

        if customer and hasattr(customer, "id"):
            airport.stripe_customer_id = customer.id
            airport.save()
            log.info(f"{airport} is now Stripe customer: {airport.stripe_customer_id}")
            return True
        else:
            message_service.post_error("Unable to create customer record in payment portal.")
    except Exception as ee:
        Error.unexpected(
            "Unable to create customer record in payment portal", ee
        )
    return False


def get_customer_from_airport(airport):
    log.trace()

    if not airport.stripe_customer_id:
        return None

    try:
        set_stripe_api_key()
        customer = stripe.Customer.retrieve(airport.stripe_customer_id)

        if customer:
            return customer
        else:
            log.error("Unable to retrieve customer record from payment portal.")
    except Exception as ee:
        Error.record(ee, airport)
    return False

def modify_customer_from_airport(airport):
    log.trace()

    if not airport.stripe_customer_id:
        return None

    try:
        set_stripe_api_key()
        customer = stripe.Customer.modify(
            airport.stripe_customer_id,
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
        )

        if customer:
            return customer
        else:
            log.error("Unable to retrieve customer record from payment portal.")
    except Exception as ee:
        Error.record(ee, airport)
    return False



def get_checkout_session_hh_subscription(airport, price_id):
    try:
        set_stripe_api_key()
        checkout_session = stripe.checkout.Session.create(
            customer=airport.stripe_customer_id,
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=f"{env.absolute_root_url}{reverse('airport:subscription_success', args=[airport.identifier])}",
            cancel_url=f"{env.absolute_root_url}{reverse('airport:subscription_failure', args=[airport.identifier])}",
        )
        co_session_id = checkout_session.id
        log.debug(f"CHECKOUT SESSION ID: {co_session_id}")
        return checkout_session
    except Exception as ee:
        Error.unexpected(
            "Unable to create a payment session", ee
        )
        return None


def get_checkout_session_application_fee(application):
    try:
        user_profile = Auth.lookup_user_profile(application.user, get_contact=True)
        customer_data = {"email": user_profile.email}
        phone = user_profile.phone_number()
        if phone:
            customer_data["phone"] = phone
        address = user_profile.contact().get_strip_address()
        if address:
            customer_data["address"] = {
                "line1": address.street_1,
                "line2": address.street_2,
                "city": address.city,
                "state": address.state,
                "postal_code": address.zip_code,
                "country": address.country,
            }
        set_stripe_api_key()
        checkout_session = stripe.checkout.Session.create(
            customer_data=customer_data,
            line_items=[
                {
                    'price_data': {
                        "unit_amount": application.airport.application_fee_stripe,
                        "product": "prod_Slrtn5xjteLKes"
                    },
                    'quantity': 1,
                },
            ],
            success_url=f"{env.absolute_root_url}{reverse('airport:subscription_success', args=[airport.identifier])}",
            cancel_url=f"{env.absolute_root_url}{reverse('airport:subscription_failure', args=[airport.identifier])}",
        )
        co_session_id = checkout_session.id
        log.debug(f"CHECKOUT SESSION ID: {co_session_id}")
        return checkout_session
    except Exception as ee:
        Error.unexpected(
            "Unable to create a payment session", ee
        )
        return None


def get_session_details(session_id):
    try:
        set_stripe_api_key()
        return stripe.checkout.Session.retrieve(session_id)
    except Exception as ee:
        Error.unexpected(
            "Unable to retrieve checkout session status", ee
        )
        return None

def get_airport_subscriptions(airport):
    if airport and airport.stripe_customer_id:
        try:
            set_stripe_api_key()
            return stripe.Subscription.list(
                customer=airport.stripe_customer_id,
                expand=['data.latest_invoice.subscription_details']
            )
        except Exception as ee:
            Error.record(
                ee, f"get_airport_subscriptions({airport})"
            )
    return None


def get_customer_portal_session(airport):
    if airport and airport.stripe_customer_id:
        try:
            set_stripe_api_key()
            session = stripe.billing_portal.Session.create(
                customer=airport.stripe_customer_id,
                return_url=f"{env.absolute_root_url}{reverse('manage:airport', args=[airport.identifier])}",
            )
            if session and hasattr(session, "url"):
                return session.url
        except Exception as ee:
            Error.record(
                ee, f"get_customer_portal_session({airport})"
            )
    return None