from base.models.utility.error import EnvHelper, Log, Error
import stripe
from base_stripe.services.config_service import set_stripe_api_key
from base_stripe.models.connected_account import StripeConnectedAccount as AccountModel
from base_stripe.classes.api.account import Account as AccountStripe

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
        response = stripe.Account.create(**params_dict)

        # If account was created...
        if response and response.get("object") == "account":
            account_stripe = AccountStripe(response)

            try:
                # Create a database record of this account for querying
                ca = AccountModel()
                ca.stripe_id = account_stripe.id
                ca.charges_enabled = account_stripe.charges_enabled
                ca.payouts_enabled = account_stripe.payouts_enabled
                ca.name = account_stripe.name
                ca.save()
                return ca

            except Exception as ee:
                Error.unexpected("Unable to save connected account record", ee)

    except Exception as ee:
        Error.unexpected("Unable to create connected account in Stripe", ee)

    return None


def create_account_onboarding_url(account_id, return_url, refresh_url=None):
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


def get_connected_account(account_id):
    """
    Get Connected Account data from Stripe
    """
    try:
        set_stripe_api_key()
        stripe_account = stripe.Account.retrieve(account_id)
        if stripe_account and stripe_account.get("object") == "account":
            ca = AccountModel.get(stripe_account.id)
            capabilities = stripe_account.get("capabilities")
            if not ca:
                log.error(f"Unable to find StripeConnectedAccount for {stripe_account.id}")
            else:
                # Sync local data with Stripe data
                ca.charges_enabled = stripe_account.get("charges_enabled")
                ca.payouts_enabled = stripe_account.get("payouts_enabled")
                ca.onboarding_complete = stripe_account.get("details_submitted")
                if capabilities:
                    ca.card_payments_enabled = capabilities.get("card_payments") == "active"
                    ca.transfers_enabled = capabilities.get("transfers") == "active"
                ca.save()

            return AccountStripe(stripe_account), ca
    except Exception as ee:
        Error.record(ee)
    return None
