from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service, utility_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.models.customer import StripeCustomer

log = Log()
env = EnvHelper()


def create_customer(full_name, email, user=None):
    """
    Create (if DNE) a Stripe customer record, and a local record that ties the Stripe ID to a User/email
    Returns local record representing the Stripe customer
    """
    log.trace([full_name, email])

    # Look for existing customer record
    existing = None
    if user:
        user_profile = Auth.lookup_user_profile(user)
        if user_profile:
            for email_address in user_profile.emails:
                existing = StripeCustomer.get(email_address)
                if existing:
                    break
    if not existing:
        existing = StripeCustomer.get(email)

    if existing:
        # full_name is only used for initial Strip Customer creation.
        # Go ahead and update it so user sees what they just entered
        existing.full_name = full_name
        try:
            existing.save()
        except Exception as ee:
            Error.unexpected(
                "Unable to update the existing customer record", ee, email
            )

        # ToDo: Sync data with Stripe data

        return existing

    # Create a new Stripe Customer
    try:
        set_stripe_api_key()
        customer = stripe.Customer.create(
            name=full_name,
            email=email,
        )
        if customer and customer.get("object") == "customer":
            stripe_id = customer.get("id")
        else:
            log.error(f"Unable to create Stripe customer: {email}")
            return None

        if user:
            customer_user = user
        else:
            # If user not provided, see if current user has the given email
            user_profile = Auth.current_user_profile()
            if email.lower() in user_profile.emails:
                customer_user = user_profile.user
            else:
                customer_user = None

        return StripeCustomer.objects.create(
            full_name=full_name, email=email, stripe_id=stripe_id, user=customer_user
        )


    except Exception as ee:
        Error.unexpected(
            "Unable to create Stripe customer record", ee, email
        )
        return None



def get_customer(customer_id):
    try:
        set_stripe_api_key()
        return stripe.Customer.retrieve(customer_id)
    except Exception as ee:
        Error.record(ee, customer_id)
        return None


def get_subscription(subscription_id):
    try:
        set_stripe_api_key()
        return stripe.Subscription.retrieve(subscription_id, expand=['latest_invoice'])
    except Exception as ee:
        Error.record(ee, subscription_id)
        return None