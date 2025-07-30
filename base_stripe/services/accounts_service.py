from base.models.utility.error import EnvHelper, Log, Error
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.classes.account import Account

log = Log()
env = EnvHelper()


def get_connected_accounts():
    accts = []
    try:
        set_stripe_api_key()
        account_list = stripe.Account.list(limit=3)
        if not account_list:
            return {}

        for acct in account_list.get("data"):
            log.debug(acct)
            accts.append(Account(acct))
    except Exception as ee:
        Error.record(ee)
    return accts


def get_connected_account(account_id):
    try:
        set_stripe_api_key()
        response = stripe.Account.retrieve(account_id)
        if response and response.get("object") == "account":
            return Account(response)
    except Exception as ee:
        Error.record(ee)
    return None


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

