from base.models.utility.error import EnvHelper, Log, Error
from base_stripe.services import config_service
import stripe
from django.utils.html import mark_safe

log = Log()
env = EnvHelper()


class Customer:
    address_stripe = None
    balance = None
    created = None
    currency = None
    default_source = None
    delinquent = None
    description = None
    discount = None
    email = None
    id = None
    invoice_prefix = None
    invoice_settings = None
        # custom_fields
        # default_payment_method
        # footer
        # rendering_options
    livemode = None
    metadata = None
    name = None
    next_invoice_sequence = None
    phone = None
    preferred_locales = None 
    shipping = None
    tax_exempt = None

    @property
    def default_payment_method(self):
        if self.invoice_settings:
            return self.invoice_settings.get("default_payment_method")
        return None

    @property
    def default_payment_method_display(self):
        pm_id = self.default_payment_method
        if pm_id:
            try:
                config_service.set_stripe_api_key()
                pm = stripe.Customer.retrieve_payment_method(self.id, pm_id)
                log.debug(f"PAYMENT METHOD:::\n{pm}\n")
                payment_type = pm.get("type")
                if payment_type == "card":
                    card = pm.get("card")
                    exp = f'exp. {card.get("exp_month")}/{card.get("exp_year")}'
                    return f'{card.get("brand")} ****{card.get("last4")} {exp}'
                elif payment_type == "us_bank_account":
                    acct = pm.get("us_bank_account")
                    return f'{acct.get("bank_name")} ****{acct.get("last4")}'
                elif payment_type == "link":
                    return mark_safe("""<a href="https://link.com" target="_blank">Link</a>""")
            except Exception as ee:
                Error.unexpected("Unable to get payment method details", ee)
                return "unknown payment method"
        else:
            return "n/a"

    @property
    def address(self):
        """
        Use keys consistent with the rest of my code
        """
        if self.address_stripe:
            return {
                "street_1": self.address_stripe.get("line1"),
                "street_2": self.address_stripe.get("line2"),
                "city": self.address_stripe.get("city"),
                "state": self.address_stripe.get("state"),
                "zip_code": self.address_stripe.get("postal_code"),
                "country": self.address_stripe.get("country"),
            }
        return {}

    @property
    def address_lines(self):
        lines = []
        if self.address_stripe:
            if self.address_stripe.get("line1"):
                lines.append(self.address_stripe.get("line1"))
            if self.address_stripe.get("line2"):
                lines.append(self.address_stripe.get("line2"))
            lines.append(
                f'{self.address_stripe.get("city")}, {self.address_stripe.get("state")} {self.address_stripe.get("postal_code")}'
            )
        return lines

    def update_stripe(self):
        """
        Update values that may be updated via the API.
        Call after updating the values in this class.
        """
        try:
            config_service.set_stripe_api_key()
            stripe.Customer.modify(
                self.id,
                address=self.address_stripe,
                description=self.description,
                email=self.email,
                metadata=self.metadata,
                name=self.name,
                phone=self.phone,
                shipping=self.shipping,
            )
            log.info("Stripe customer has been updated")
        except Exception as ee:
            Error.unexpected("Unable to update customer record in Stripe", ee)


    def __init__(self, api_response):
        if api_response:
            log.debug(api_response)
            self.address_stripe = api_response.get("address")
            self.balance = api_response.get("balance")
            self.created = api_response.get("created")
            self.currency = api_response.get("currency")
            self.default_source = api_response.get("default_source")
            self.delinquent = api_response.get("delinquent")
            self.description = api_response.get("description")
            self.discount = api_response.get("discount")
            self.email = api_response.get("email")
            self.id = api_response.get("id")
            self.invoice_prefix = api_response.get("invoice_prefix")
            self.invoice_settings = api_response.get("invoice_settings")
            # custom_fields
            # default_payment_method
            # footer
            # rendering_options
            self.livemode = api_response.get("livemode")
            self.metadata = api_response.get("metadata")
            self.name = api_response.get("name")
            self.next_invoice_sequence = api_response.get("next_invoice_sequence")
            self.phone = api_response.get("phone")
            self.preferred_locales = api_response.get("preferred_locales")
            self.shipping = api_response.get("shipping")
            self.tax_exempt = api_response.get("tax_exempt")
        