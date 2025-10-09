
from base.models.utility.error import EnvHelper, Log, Error
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.models.payment_models import StripeCheckoutSession, StripeSubscription, StripeCustomer
import stripe

log = Log()
env = EnvHelper()


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


def get_stripe_customer_id(source):
    """
    Return a Stripe customer ID (string)

    Parameter: source may be any model, class, or string that can point to a Customer
    """
    c = get_stripe_customer(source)
    return c.stripe_id if c else None