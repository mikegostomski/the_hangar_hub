from base.models.utility.error import EnvHelper, Log, Error
import stripe
from decimal import Decimal
from django.urls import reverse

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


def get_checkout_session_hh_subscription(airport, price_id):
    try:
        set_stripe_api_key()
        checkout_session = stripe.checkout.Session.create(
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
        return checkout_session
    except Exception as ee:
        Error.unexpected(
            "Unable to create a payment session", ee
        )
        return None


