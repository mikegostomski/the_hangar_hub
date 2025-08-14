from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service, utility_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.models.customer import Customer as CustomerModel
from base_stripe.classes.api.customer import Customer as StripeCustomer


log = Log()
env = EnvHelper()

"""
These functions deal with the Customer object in Stripe.
There is also a local Customer model that links Users to their Customer record in Stripe

The Customer object in Stripe will be referenced as stripe_customer
The local Customer object will be referenced as customer_model

stripe_customer data will be stored in base_stripe.classes.api.Customer for code completion features
"""

def create_stripe_customer(full_name=None, email=None, user=None):
    """
    Create (if DNE) a Customer record in Stripe, and a local record that ties the Stripe ID to a User/email

    Parameters:
        Must provide full_name AND email, or a user object (all three may be provided)

    Returns local record representing the Stripe customer (customer_model)
    """
    log.trace([full_name, email, user])

    user_profile = Auth.lookup_user_profile(user) if user else None

    if user_profile is None and not (full_name and email):
        message_service.post_error("Full name and email address must be provided to create a Customer record in Stripe")
        return None

    if not full_name:
        full_name = user_profile.display_name
    if not email:
        email = user_profile.email

    # If user was not provided, look for one via email address
    if not user_profile:
        user_profile = Auth.lookup_user_profile(email)
        if user_profile:
            user = user_profile.user

    # Look for existing customer record
    existing = None
    if user:
        # Look for ANY verified email address for this user
        user_profile = Auth.lookup_user_profile(user)
        if user_profile:
            for email_address in user_profile.emails:
                existing = CustomerModel.get(email_address)
                if existing:
                    break
    if not existing:
        existing = CustomerModel.get(email)

    if existing:
        # ToDo: Sync data with Stripe data?
        return existing

    # Create a new Stripe Customer
    try:
        set_stripe_api_key()
        stripe_customer = stripe.Customer.create(
            name=full_name,
            email=email,
        )
        # API either succeeds or raises an exception
        stripe_id = stripe_customer.get("id")

        # Create and return customer_model
        return CustomerModel.objects.create(
            full_name=full_name, email=email, stripe_id=stripe_id, user=user
        )

    except Exception as ee:
        Error.unexpected("Unable to create Stripe customer record", ee, email)
        return None


def get_stripe_customer(customer):
    """
    Gets the Customer object from stripe for specified user.
    If no record exists in Stripe, one will be created.

    Parameter:
     - The Stripe ID of the customer, a User, UserProfile, or email

    Returns: stripe_customer
    """
    stripe_id = None
    if type(customer) is str and customer.startswith("cus_"):
        stripe_id = customer
    else:
        user = Auth.lookup_user(customer)
        if user:
            customer_model = create_stripe_customer(user=user)
            if customer_model:
                stripe_id = customer_model.stripe_id

    if not stripe_id:
        message_service.post_error("Unable to determine customer's Stripe ID")
        return None

    try:
        set_stripe_api_key()
        return StripeCustomer(stripe.Customer.retrieve(stripe_id))
    except Exception as ee:
       Error.unexpected("Unable to locate customer in Stripe", ee, stripe_id)
    return None


def get_customer_model(customer):
    return CustomerModel.get(customer)




def customer_has_payment_method(customer_id):
    customer = get_stripe_customer(customer_id)

    # Does customer have a payment method saved in Stripe?
    default_pay_method = customer.get("invoice_settings", {}).get("default_payment_method")
    default_source = customer.get("default_source")
    return default_pay_method or default_source



def get_subscription(subscription_id):
    # ToDo: Should this be here, or in a subscription_service?
    try:
        set_stripe_api_key()
        return stripe.Subscription.retrieve(subscription_id, expand=['latest_invoice'])
    except Exception as ee:
        Error.record(ee, subscription_id)
        return None