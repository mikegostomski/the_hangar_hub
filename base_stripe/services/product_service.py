from base.models.utility.error import EnvHelper, Log, Error
import stripe
from base_stripe.services.config_service import set_stripe_api_key
from base_stripe.classes.price import Price
from base_stripe.models.product_models import StripeProduct, StripePrice
from base_stripe.models.connected_account import StripeConnectedAccount


log = Log()
env = EnvHelper()


def get_products():
    return StripeProduct.objects.prefetch_related('prices').all()

def get_product_query():
    return StripeProduct.objects.prefetch_related('prices')


def get_price_list(account=None):
    prices = []
    try:
        set_stripe_api_key()
        if account:
            account = StripeConnectedAccount.get(account)
            price_list = stripe.Price.list(expand=['data.product'], stripe_account=account.stripe_id)
        else:
            price_list = stripe.Price.list(expand=['data.product'])
        if not price_list:
            return {}

        for pp in price_list.get("data"):
            price_instance = Price(pp)
            prices.append(price_instance)
    except Exception as ee:
        Error.record(ee)
    return prices

