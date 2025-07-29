from base.models.utility.error import EnvHelper, Log, Error
from decimal import Decimal

log = Log()
env = EnvHelper()


class Price:
    id = None
    lookup_key = None
    product_id = None
    name = None
    description = None
    recurring = None
    trial_days = None
    amount_cents = None

    def amount(self):
        if self.amount_cents and str(self.amount_cents).isnumeric():
            return Decimal(self.amount_cents / 100)
        else:
            return None

    def __init__(self, api_dict):
        self.id = api_dict.get("id")
        self.lookup_key = api_dict.get("lookup_key") or self.id
        try:
            self.amount_cents = int(api_dict.get("unit_amount_decimal"))
        except Exception as ee:
            Error.record(ee, api_dict)

        if api_dict["product"]:
            self.product_id = api_dict["product"].get("id")
            self.name = api_dict["product"].get("name")
            self.description = api_dict["product"].get("description")
        if api_dict["recurring"]:
            self.recurring = api_dict["recurring"].get("interval")
            self.trial_days = api_dict["recurring"].get("trial_period_days")


