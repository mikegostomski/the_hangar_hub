from base.models.utility.error import EnvHelper, Log, Error
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.classes.account import Account
from base_stripe.models.connected_account import ConnectedAccount

log = Log()
env = EnvHelper()


def create_account(params_dict):

    try:
        set_stripe_api_key()
        account_object = stripe.Account.create(**params_dict)
        if account_object and account_object.get("object") == "account":
            try:
                ca = ConnectedAccount()
                ca.stripe_id = account_object.get("id")
                ca.charges_enabled = account_object.get("charges_enabled")
                ca.payouts_enabled = account_object.get("payouts_enabled")

                business_profile = account_object.get("business_profile")
                company = account_object.get("company")

                if business_profile:
                    ca.name = business_profile.get("name")
                elif company:
                    ca.name = company.get("name")
                else:
                    # ToDo: Individual name?
                    ca.name = f"Account: {ca.stripe_id}"

                ca.save()
                return ca

            except Exception as ee:
                Error.unexpected(
                    "Unable to save connected account record", ee
                )

    except Exception as ee:
        Error.unexpected(
            "Unable to create connected account in Stripe", ee
        )

    return None



def create_account_onboarding_link(account_id, return_url, refresh_url=None):
    log.trace([account_id, return_url, refresh_url])
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
        return link
    except Exception as ee:
        Error.unexpected(
            "Unable to create onboarding link to Stripe", ee
        )

    return None


def create_account_login_link(account_id, return_url, refresh_url=None):
    log.trace([account_id, return_url, refresh_url])
    try:
        abs_url = env.absolute_root_url
        if return_url and not return_url.startswith(abs_url):
            return_url = f"{abs_url}{return_url}"
        if refresh_url and not refresh_url.startswith(abs_url):
            refresh_url = f"{abs_url}{refresh_url}"

        set_stripe_api_key()
        link = stripe.AccountLink.create(
            account=account_id,
            type="account_update",
            return_url=return_url,
            refresh_url=refresh_url or return_url,
        )
        return link
    except Exception as ee:
        Error.unexpected(
            "Unable to create account login link to Stripe", ee
        )

    return None



def get_connected_account(account_id):
    try:
        set_stripe_api_key()
        stripe_account = stripe.Account.retrieve(account_id)
        if stripe_account and stripe_account.get("object") == "account":
            ca = ConnectedAccount.get(stripe_account.id)
            capabilities = stripe_account.get("capabilities")
            if not ca:
                log.error(f"Unable to find ConnectedAccount for {stripe_account.id}")
            else:
                # Sync local data with Stripe data
                ca.charges_enabled = stripe_account.get("charges_enabled")
                ca.payouts_enabled = stripe_account.get("payouts_enabled")
                ca.onboarding_complete = stripe_account.get("details_submitted")
                if capabilities:
                    ca.card_payments_enabled = capabilities.get("card_payments") == "active"
                    ca.transfers_enabled = capabilities.get("transfers") == "active"
                ca.save()

            return stripe_account, ca
    except Exception as ee:
        Error.record(ee)
    return None














def get_connected_accounts():
    accts = []
    try:
        set_stripe_api_key()
        account_list = stripe.Account.list(limit=3)
        if not account_list:
            return {}

        for acct in account_list.get("data"):
            accts.append(Account(acct))
    except Exception as ee:
        Error.record(ee)
    return accts



def modify_connected_account(account_instance):
    try:
        set_stripe_api_key()
        response = stripe.Account.modify(
            account_instance.id,
            business_profile={"name": account_instance.name, "support_phone": account_instance.company_phone,},
            company={
                "name": account_instance.company_name,
                "phone": account_instance.company_phone,
                "address": account_instance.company_stripe_address(),
            }

        )
        if response and response.get("object") == "account":
            return Account(response)
    except Exception as ee:
        Error.record(ee)
    return None

