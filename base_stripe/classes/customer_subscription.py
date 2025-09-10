from base.models.utility.error import EnvHelper, Log, Error
from decimal import Decimal
from base.services import date_service
import stripe
from base_stripe.services.config_service import set_stripe_api_key
from base_stripe.models.payment_models import Customer

log = Log()
env = EnvHelper()


class CustomerSubscription:
    subscription_data = None
    customer_class = None
    invoice_data = None

    # IDs
    # ..........................................................................
    @property
    def id(self):
        return self.subscription_data.get("id")

    @property
    def customer_id(self):
        return self.subscription_data.get("customer")

    @property
    def latest_invoice_id(self):
        return self.invoice_data.get("id")


    # Statuses
    # ..........................................................................
    @property
    def status(self):
        return self.subscription_data.get("status")

    @property
    def invoice_status(self):
        return self.invoice_data.get("status")

    @property
    def automatically_finalizes_at(self):
        """When 'draft' status becomes 'open' """
        if self.invoice_data:
            return date_service.string_to_date(self.invoice_data.get("automatically_finalizes_at"))

    @property
    def delinquent(self):
        return self.customer_class.delinquent


    # Latest Invoice Data
    # ..........................................................................
    @property
    def invoice_id(self):
        if self.invoice_data:
            return self.invoice_data.get("id")

    @property
    def invoice_pdf(self):
        if self.invoice_data:
            return self.invoice_data.get("invoice_pdf")

    @property
    def invoice_lines(self):
        if self.invoice_data:
            return list(self.invoice_data["lines"].data or [])
        return [{}]

    @property
    def invoice_items(self):
        if self.invoice_data:
            return [{"description": x.get("description"), "amount": (x.get("amount") or 0)/100} for x in self.invoice_lines]
        return [{}]

    @property
    def period_start(self):
        if self.invoice_data:
            return date_service.string_to_date(self.invoice_data["lines"].data[0]["period"]["start"])

    @property
    def period_end(self):
        if self.invoice_data:
            return date_service.string_to_date(self.invoice_data["lines"].data[0]["period"]["end"])
    
    @property
    def amount_due(self):
        if self.invoice_data:
            return Decimal(self.invoice_data.get("amount_due")/100)

    @property
    def amount_paid(self):
        if self.invoice_data:
            return Decimal(self.invoice_data.get("amount_paid")/100)

    @property
    def amount_remaining(self):
        if self.invoice_data:
            return Decimal(self.invoice_data.get("amount_remaining")/100)

    @property
    def due_date(self):
        if self.invoice_data:
            return date_service.string_to_date(self.invoice_data.get("due_date"))

    @property
    def billing_cycle_anchor(self):
        return date_service.string_to_date(self.subscription_data.get("billing_cycle_anchor"))

    @property
    def billing_cycle_day(self):
        return self.subscription_data.get("billing_cycle_anchor_config").get("day_of_month")


    # Subscription Cancellation Data
    # ..........................................................................
    
    @property
    def cancel_at(self):
        return date_service.string_to_date(self.subscription_data.get("cancel_at"))

    @property
    def canceled_at(self):
        return date_service.string_to_date(self.subscription_data.get("canceled_at"))

    @property
    def cancel_at_period_end(self):
        return self.subscription_data.get("cancel_at_period_end")

    @property
    def cancel_comment(self):
        return self.subscription_data.get("cancellation_details").get("comment")

    @property
    def cancel_feedback(self):
        return self.subscription_data.get("cancellation_details").get("feedback")

    @property
    def cancel_reason(self):
        return self.subscription_data.get("cancellation_details").get("reason")


    def __init__(self, subscription_id):
        self.subscription_data = stripe.Subscription.retrieve(subscription_id, expand=['latest_invoice']) or {}
        self.invoice_data = self.subscription_data.get("latest_invoice") or {}
        self.customer_class = Customer.get(self.customer_id).api_wrapper() or {}



