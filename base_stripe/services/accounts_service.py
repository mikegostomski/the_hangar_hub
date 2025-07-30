from base.models.utility.error import EnvHelper, Log, Error
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service
from base_stripe.services.config_service import set_stripe_api_key
from base_stripe.classes.account import Account

log = Log()
env = EnvHelper()


def get_connected_accounts():
    accts = []
    try:
        set_stripe_api_key()
        account_list = accounts = stripe.Account.list(limit=3)
        if not account_list:
            return {}

        for acct in account_list.get("data"):
            log.debug(acct)
            accts.append(Account(acct))
    except Exception as ee:
        Error.record(ee)
    return accts

