from base.models.utility.error import EnvHelper, Log, Error
import stripe


log = Log()
env = EnvHelper()

def set_stripe_api_key():
    stripe.api_key = env.get_setting("STRIPE_KEY")


def get_stripe_address_dict(
        street_1=None, street_2=None, city=None, state=None, zip_code=None, country=None,
        address_instance=None
):
    """
    Stripe addresses need to be passed in a dict with specific keys
    """
    if address_instance:
        return {
            "line1": address_instance.street_1,
            "line2": address_instance.street_2,
            "city": address_instance.city,
            "state": address_instance.state,
            "postal_code": address_instance.zip_code,
            "country": address_instance.country,
        }
    else:
        return {
            "line1": street_1,
            "line2": street_2,
            "city": city,
            "state": state,
            "postal_code": zip_code,
            "country": country,
        }
