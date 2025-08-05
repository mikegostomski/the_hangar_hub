from base.models.utility.error import EnvHelper, Log, Error
from decimal import Decimal
from base_stripe.services import customer_service
from base.services import date_service

log = Log()
env = EnvHelper()


class CustomerSubscription:
    subscription_data = None
    customer_data = None
    invoice_data = None

    @property
    def id(self):
        return self.subscription_data.get("id")

    @property
    def customer_id(self):
        return self.subscription_data.get("customer")

    @property
    def latest_invoice_id(self):
        return self.invoice_data.get("id")

    @property
    def amount_due(self):
        return Decimal(self.invoice_data.get("amount_due")/100)

    @property
    def amount_paid(self):
        return Decimal(self.invoice_data.get("amount_paid")/100)

    @property
    def amount_remaining(self):
        return Decimal(self.invoice_data.get("amount_remaining")/100)

    @property
    def period_start(self):
        return date_service.string_to_date(self.invoice_data["lines"].data[0]["period"]["start"])

    @property
    def period_end(self):
        return date_service.string_to_date(self.invoice_data["lines"].data[0]["period"]["end"])

    @property
    def description(self):
        return self.subscription_data.get("description")

    @property
    def collection_method(self):
        return self.subscription_data.get("collection_method")

    @property
    def status(self):
        return self.subscription_data.get("status")

    @property
    def start_date(self):
        return date_service.string_to_date(self.subscription_data.get("start_date"))

    @property
    def billing_cycle_anchor(self):
        return date_service.string_to_date(self.subscription_data.get("billing_cycle_anchor"))

    @property
    def billing_cycle_day(self):
        return self.subscription_data.get("billing_cycle_anchor_config").get("day_of_month")

    @property
    def cancel_at(self):
        return date_service.string_to_date(self.subscription_data.get("cancel_at"))

    @property
    def canceled_at(self):
        return date_service.string_to_date(self.subscription_data.get("canceled_at"))


    def __init__(self, subscription_id):
        self.subscription_data = customer_service.get_subscription(subscription_id) or {}
        self.invoice_data = self.subscription_data.get("latest_invoice")
        self.customer_data = customer_service.get_customer(self.customer_id) or {}



