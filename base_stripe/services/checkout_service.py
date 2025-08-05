from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service, utility_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict

log = Log()
env = EnvHelper()


def verify_checkout(checkout_id=None, session_var=None, account_id=None):
    log.trace([checkout_id, session_var, account_id])
    success = False
    try:
        if checkout_id is None:
            checkout_id = env.get_session_variable(session_var)

        if not str(checkout_id).startswith("cs_"):
            log.error("Checkout session ID could not be located")
            return None


        set_stripe_api_key()
        if account_id:
            checkout = stripe.checkout.Session.retrieve(checkout_id, stripe_account=account_id)
        else:
            checkout = stripe.checkout.Session.retrieve(checkout_id)

        if checkout and checkout.get("object") == "checkout.session":
            payment_status = checkout.get("payment_status")
            tx_status = checkout.get("status")
            amount_total_cents = checkout.get("amount_total")
            success = (tx_status == "complete" and payment_status == "paid")

            if success:
                Auth.audit(
                    "C", "STRIPE", f"Completed Stripe payment: {checkout_id}",
                    new_value=utility_service.format_decimal(amount_total_cents*100)
                )
            else:
                Auth.audit(
                    "C", "STRIPE", f"Incomplete Stripe payment: {checkout_id}",
                    new_value=f"{tx_status}|{payment_status}"
                )

    except Exception as ee:
        Error.unexpected(
            "Unable to verify checkout status from Stripe", ee, checkout_id
        )

    return success
