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

    Note: Countries must be two-digit code. Only using US and CA for now, but if others in the future:
    https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2#Officially_assigned_code_elements
    """
    if address_instance:
        country = address_instance.country[:2] if address_instance.country in ["USA", "CAN"] else address_instance.country
        return {
            "line1": address_instance.street_1,
            "line2": address_instance.street_2,
            "city": address_instance.city,
            "state": address_instance.state,
            "postal_code": address_instance.zip_code,
            "country": country,
        }
    else:
        country = country[:2] if country in ["USA", "CAN"] else country
        return {
            "line1": street_1,
            "line2": street_2,
            "city": city,
            "state": state,
            "postal_code": zip_code,
            "country": country,
        }
