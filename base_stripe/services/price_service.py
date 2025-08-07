from base.models.utility.error import EnvHelper, Log, Error
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service
from base_stripe.services.config_service import set_stripe_api_key
from base_stripe.classes.price import Price

log = Log()
env = EnvHelper()

# ToDo: Is this still needed for anything?


def get_price_list():
    prices = []
    try:
        set_stripe_api_key()
        price_list = stripe.Price.list(
            expand=['data.product']
        )
        if not price_list:
            return {}

        for pp in price_list.get("data"):
            price_instance = Price(pp)
            prices.append(price_instance)
    except Exception as ee:
        Error.record(ee)
    return prices

