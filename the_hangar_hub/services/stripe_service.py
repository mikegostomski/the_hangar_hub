from base.models.utility.error import EnvHelper, Log, Error
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service

log = Log()
env = EnvHelper()

def set_stripe_api_key():
    stripe.api_key = env.get_setting("STRIPE_KEY")


def get_price_data():
    prices = {}
    try:
        set_stripe_api_key()
        price_list = stripe.Price.list(
            expand=['data.product']
        )
        if not price_list:
            return {}

        for pp in price_list:
            lookup_key = pp.get("lookup_key")
            price_id = pp.get("id")
            name = pp["product"].get("name")
            description = pp["product"].get("description")
            recurring = pp["recurring"].get("interval")
            trial_days = pp["recurring"].get("trial_period_days")
            amount_cents = int(pp.get("unit_amount_decimal"))
            amount_dollars = Decimal(amount_cents/100)
            prices[lookup_key] = {
                "id": price_id,
                "name": name,
                "description": description,
                "recurring": recurring,
                "trial_days": trial_days,
                "amount_dollars": amount_dollars
            }
    except Exception as ee:
        Error.record(ee)
    return prices


def get_subscription_prices():
    return {lookup_key: data for  lookup_key, data in get_price_data().items() if data["name"] == "The Hangar Hub"}


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
            address={
                "line1": airport.billing_street_1,
                "line2": airport.billing_street_2,
                "city": airport.billing_city,
                "state": airport.billing_state,
                "postal_code": airport.billing_zip,
                "country": airport.country,
            },
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
            address={
                "line1": airport.billing_street_1,
                "line2": airport.billing_street_2,
                "city": airport.billing_city,
                "state": airport.billing_state,
                "postal_code": airport.billing_zip,
                "country": airport.country,
            },
        )

        if customer:
            return customer
        else:
            log.error("Unable to retrieve customer record from payment portal.")
    except Exception as ee:
        Error.record(ee, airport)
    return False


# def create_subscription(airport, price_id):
#     customer_id = airport.stripe_customer_id
#     if not customer_id:
#         create_customer_from_airport(airport)
#
#     try:
#         set_stripe_api_key()
#
#         # Create the subscription
#         subscription = stripe.Subscription.create(
#             customer=customer_id,
#             items=[{
#                 'price': price_id,
#             }],
#             payment_behavior='default_incomplete',
#             expand=['latest_invoice.payment_intent'],
#         )
#         log.debug(subscription)
#         return subscription
#
#     except Exception as ee:
#         Error.unexpected("Unable to create subscription", ee)
#     return None


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