from base.models.utility.error import EnvHelper, Log, Error
import stripe
from base_stripe.services.config_service import set_stripe_api_key
from base_stripe.models.connected_account import StripeConnectedAccount

log = Log()
env = EnvHelper()


def create_account(params_dict):
    """
    Create a Connect Account in Stripe
    Create a local record of this as well

    Returns: the local record (model) for this Account
    """
    try:
        # Create the Account in Stripe
        set_stripe_api_key()
        stripe_account = stripe.Account.create(**params_dict)
        try:
            # Create a database record of this account for querying
            return StripeConnectedAccount.from_stripe_id(stripe_account.id)
        except Exception as ee:
            Error.unexpected("Unable to save connected account record", ee)
    except Exception as ee:
        Error.unexpected("Unable to create connected account in Stripe", ee)
    return None


def get_account_onboarding_url(account_id, return_url, refresh_url=None):
    """
    Link to Stripe session for onboarding, as well as making account changes after onboarding
    """
    try:
        abs_url = env.absolute_root_url
        if return_url and not return_url.startswith(abs_url):
            return_url = f"{abs_url}{return_url}"
        if refresh_url and not refresh_url.startswith(abs_url):
            refresh_url = f"{abs_url}{refresh_url}"

        set_stripe_api_key()
        link = stripe.AccountLink.create(
            account=account_id,
            type="account_onboarding",
            collection_options={"fields": "eventually_due", "future_requirements": "include"},
            return_url=return_url,
            refresh_url=refresh_url or return_url,
        )
        return link.url
    except Exception as ee:
        Error.unexpected("Unable to create onboarding link to Stripe", ee)
    return None

