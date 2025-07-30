from base.models.utility.error import EnvHelper, Log, Error
from decimal import Decimal
from base_stripe.services.config_service import get_stripe_address_dict

log = Log()
env = EnvHelper()


class Account:
    id = None
    name = None
    fee_payer = None
    loss_payer = None
    requirement_collection = None
    default_currency = None
    login_link = None
    payouts_enabled = None
    company_name = None
    company_phone = None
    company_address = None

    def editable_attrs(self):
        return [
            "name",
            "company_name", "company_phone",
            "street_1", "street_2", "city", "state", "zip_code", "country",
        ]

    def set_phone(self, new_phone):
        self.company_phone = new_phone
        # if self.company_phone and len(self.company_phone) == 10:
        #     self.company_phone = f"+1{self.company_phone}"

    def company_stripe_address(self):
        if type(self.company_address) is dict:
            return get_stripe_address_dict(**self.company_address)
        else:
            return None

    def __init__(self, api_data):
        self.id = api_data.get("id")
        self.fee_payer = api_data.get("controller").get("fees").get("payer")
        self.loss_payer = api_data.get("controller").get("losses").get("payments")
        self.requirement_collection = api_data.get("controller").get("requirement_collection")
        self.default_currency = api_data.get("default_currency")
        self.payouts_enabled = api_data.get("payouts_enabled")

        co = api_data.get("company")
        if co:
            self.company_name = co.get("name")
            self.company_phone = co.get("phone")

            ad = co.get("address")
            if ad:
                # Match base.models.contact.Address format
                self.company_address = {
                    "street_1": ad.get("line1"),
                    "street_2": ad.get("line2"),
                    "city": ad.get("city"),
                    "state": ad.get("state"),
                    "zip_code": ad.get("postal_code"),
                    "country": ad.get("country"),
                }
            else:
                self.company_address = {
                    "street_1": None,
                    "street_2": None,
                    "city": None,
                    "state": None,
                    "zip_code": None,
                    "country": None,
                }

        ll = api_data.get("login_links")
        self.login_link = ll.get("url") if ll else None

        profile = api_data.get("business_profile")
        if profile:
            self.name = profile.get("name")