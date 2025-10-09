from django.http import HttpResponseForbidden

from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service, utility_service, date_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.services import price_service, accounts_service, invoice_service
from base_stripe.models.connected_account import StripeConnectedAccount
from base_stripe.models.payment_models import StripeSubscription
from base_stripe.models.payment_models import StripeCustomer
from base_stripe.models.payment_models import StripeInvoice as StripeInvoice
from datetime import datetime, timezone, timedelta
from the_hangar_hub.models.rental_models import RentalAgreement
from the_hangar_hub.services import airport_service

log = Log()
env = EnvHelper()


def webhook_reaction_needed(needed=False):
    """
    Call with True to indicate that webhooks need to be checked on the next page load
    This will be called and reacted to by context processing
    """
    if needed:
        return env.set_flash_scope("react_to_stripe_webhooks", True)
    else:
        return env.get_flash_scope("react_to_stripe_webhooks")

def get_stripe_customer_id(source):
    """
    Return a Stripe customer ID (string)

    Parameter: source may be any model, class, or string that can point to a Customer
    """
    c = get_stripe_customer(source)
    return c.stripe_id if c else None


def get_stripe_customer(source):
    """
    Return a base_stripe.StripeCustomer (model)
    
    Parameter: source may be any model, class, or string that can point to a Customer
    """
    log.trace([source])
    try:
        module = source.__class__.__module__
        class_name = source.__class__.__name__

        if "base_stripe" in module:
            if class_name == "StripeCustomer":
                return source  # Was already a StripeCustomer model
            elif class_name in ["StripeInvoice", "StripeSubscription"]:
                return source.customer
            else:
                log.error(f"Cannot obtain customer from {module}.{class_name}")
                return None

        elif "hangar_hub" in module:
            if class_name == "Airport":
                return StripeCustomer.get(source.stripe_customer_id) if source.stripe_customer_id else None

            elif class_name == "Application":
                return StripeCustomer.get_or_create(user=source.user)

            elif class_name == "Tenant":
                tenant = source
                if not tenant.customer:
                    tenant.customer = StripeCustomer.get_or_create(source.display_name, source.email, source.user)
                    tenant.save()
                return tenant.customer

            elif class_name == "RentalAgreement":
                tenant = source.tenant
                if not tenant.customer:
                    tenant.customer = StripeCustomer.get_or_create(source.display_name, source.email, source.user)
                    tenant.save()
                return tenant.customer

            elif class_name == "RentalInvoice":
                tenant = source.agreement.tenant
                if not tenant.customer:
                    tenant.customer = StripeCustomer.get_or_create(source.display_name, source.email, source.user)
                    tenant.save()
                return tenant.customer

        else:
            # Handles email, stripe_id, Customer ID, etc
            return StripeCustomer.get(source)

    except Exception as ee:
        Error.unexpected("Unable to obtain Stripe customer record", ee)
        return None


def next_anchor_date(from_date, anchor_day_number):
    """
    Given a datetime, get the next billing anchor date (could be same date)
    (essentially gets the same day next month, or uses the given date)
    """
    from_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
    if int(from_date.day) < anchor_day_number:
        return int(from_date.replace(day=anchor_day_number).timestamp())
    elif int(from_date.day) > anchor_day_number:
        if from_date.month == 12:
            return int(from_date.replace(month=1, day=anchor_day_number, year=from_date.year + 1).timestamp())
        else:
            return int(from_date.replace(month=from_date.month + 1, day=anchor_day_number).timestamp())
    else:
        return int(from_date.timestamp())