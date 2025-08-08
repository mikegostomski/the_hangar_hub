from base.models.utility.error import EnvHelper, Log, Error
from base_stripe.services import config_service
from base.services import date_service
import stripe
from decimal import Decimal

log = Log()
env = EnvHelper()


class Invoice:
    id = None
    account_country = None
    account_name = None
    account_tax_ids = None
    amount_due = None
    amount_paid = None
    amount_overpaid = None
    amount_remaining = None
    amount_shipping = None
    application = None
    attempt_count = None
    attempted = None
    auto_advance = None
    automatic_tax = None
    billing_reason = None
    collection_method = None
    created = None
    currency = None
    custom_fields = None
    customer = None
    customer_address = None
    customer_email = None
    customer_name = None
    customer_phone = None
    customer_shipping = None
    customer_tax_exempt = None
    customer_tax_ids = None
    confirmation_secret = None
    default_payment_method = None
    default_source = None
    default_tax_rates = None
    description = None
    discounts = None
    due_date = None
    effective_at = None
    ending_balance = None
    footer = None
    from_invoice = None
    hosted_invoice_url = None
    invoice_pdf = None
    issuer = None
    last_finalization_error = None
    latest_revision = None
    lines = None
        # object = None
        # data = None
        # has_more = None
        # total_count = None
        # url = None
    payments = None
        # object = None
        # data = None
        # has_more = None
        # total_count = None
        # url = None
    livemode = None
    metadata = None
    next_payment_attempt = None
    number = None
    on_behalf_of = None
    parent = None
    payment_settings = None
    period_end = None
    period_start = None
    post_payment_credit_notes_amount = None
    pre_payment_credit_notes_amount = None
    receipt_number = None
    shipping_cost = None
    shipping_details = None
    starting_balance = None
    statement_descriptor = None
    status = None
    status_transitions = None
        # finalized_at = None
        # marked_uncollectible_at = None
        # paid_at = None
        # voided_at = None
    subtotal = None
    subtotal_excluding_tax = None
    test_clock = None
    total = None
    total_discount_amounts = None
    total_excluding_tax = None
    total_taxes = None
    transfer_data = None
    webhooks_delivered_at = None

    # Dates must be converted to datetime objects
    # ......................................................
    @property
    def date_invoice(self):
        if self.effective_at:
            return date_service.string_to_date(self.effective_at)

    @property
    def date_due(self):
        if self.due_date:
            return date_service.string_to_date(self.due_date)


    # Amounts must be converted to dollars
    # ......................................................

    @property
    def dollars_due(self):
        return Decimal(self.amount_due/100) if self.amount_due else None

    @property
    def dollars_paid(self):
        return Decimal(self.amount_paid/100) if self.amount_paid else None

    @property
    def dollars_overpaid(self):
        return Decimal(self.amount_overpaid/100) if self.amount_overpaid else None

    @property
    def dollars_remaining(self):
        return Decimal(self.amount_remaining/100) if self.amount_remaining else None

    @property
    def dollars_shipping(self):
        return Decimal(self.amount_shipping/100) if self.amount_shipping else None

    @property
    def dollars_subtotal(self):
        return Decimal(self.subtotal/100) if self.subtotal else None

    @property
    def dollars_total(self):
        return Decimal(self.total/100) if self.total else None

    # ......................................................

    @property
    def invoice_lines(self):
        return list(self.lines.data or []) if self.lines else []

    @property
    def invoice_items(self):
        return [{"description": x.get("description"), "amount": (x.get("amount") or 0) / 100} for x in self.invoice_lines]

    @property
    def billing_periods(self):
        periods = list(set([(x.get("period").get("start"), x.get("period").get("end")) for x in self.invoice_lines]))
        return [{"start": date_service.string_to_date(x[0]), "end": date_service.string_to_date(x[1])} for x in periods]

    @property
    def auto_pay(self):
        return self.collection_method == "charge_automatically"

    @property
    def interactive_url(self):
        return self.hosted_invoice_url

    @property
    def pdf_url(self):
        return self.invoice_pdf

    
    def __init__(self, api_response):
        if api_response:
            log.debug(api_response)
            self.id = api_response.get("id")
            self.account_country = api_response.get("account_country")
            self.account_name = api_response.get("account_name")
            self.account_tax_ids = api_response.get("account_tax_ids")
            self.amount_due = api_response.get("amount_due")
            self.amount_paid = api_response.get("amount_paid")
            self.amount_overpaid = api_response.get("amount_overpaid")
            self.amount_remaining = api_response.get("amount_remaining")
            self.amount_shipping = api_response.get("amount_shipping")
            self.application = api_response.get("application")
            self.attempt_count = api_response.get("attempt_count")
            self.attempted = api_response.get("attempted")
            self.auto_advance = api_response.get("auto_advance")
            self.automatic_tax = api_response.get("automatic_tax")
            self.billing_reason = api_response.get("billing_reason")
            self.collection_method = api_response.get("collection_method")
            self.created = api_response.get("created")
            self.currency = api_response.get("currency")
            self.custom_fields = api_response.get("custom_fields")
            self.customer = api_response.get("customer")
            self.customer_address = api_response.get("customer_address")
            self.customer_email = api_response.get("customer_email")
            self.customer_name = api_response.get("customer_name")
            self.customer_phone = api_response.get("customer_phone")
            self.customer_shipping = api_response.get("customer_shipping")
            self.customer_tax_exempt = api_response.get("customer_tax_exempt")
            self.customer_tax_ids = api_response.get("customer_tax_ids")
            self.confirmation_secret = api_response.get("confirmation_secret")
            self.default_payment_method = api_response.get("default_payment_method")
            self.default_source = api_response.get("default_source")
            self.default_tax_rates = api_response.get("default_tax_rates")
            self.description = api_response.get("description")
            self.discounts = api_response.get("discounts")
            self.due_date = api_response.get("due_date")
            self.effective_at = api_response.get("effective_at")
            self.ending_balance = api_response.get("ending_balance")
            self.footer = api_response.get("footer")
            self.from_invoice = api_response.get("from_invoice")
            self.hosted_invoice_url = api_response.get("hosted_invoice_url")
            self.invoice_pdf = api_response.get("invoice_pdf")
            self.issuer = api_response.get("issuer")
            self.last_finalization_error = api_response.get("last_finalization_error")
            self.latest_revision = api_response.get("latest_revision")
            self.lines = api_response.get("lines")
            # self.object = api_response.get("object")
            # self.data = api_response.get("data")
            # self.has_more = api_response.get("has_more")
            # self.total_count = api_response.get("total_count")
            # self.url = api_response.get("url")
            self.payments = api_response.get("payments")
            # self.object = api_response.get("object")
            # self.data = api_response.get("data")
            # self.has_more = api_response.get("has_more")
            # self.total_count = api_response.get("total_count")
            # self.url = api_response.get("url")
            self.livemode = api_response.get("livemode")
            self.metadata = api_response.get("metadata")
            self.next_payment_attempt = api_response.get("next_payment_attempt")
            self.number = api_response.get("number")
            self.on_behalf_of = api_response.get("on_behalf_of")
            self.parent = api_response.get("parent")
            self.payment_settings = api_response.get("payment_settings")
            self.period_end = api_response.get("period_end")
            self.period_start = api_response.get("period_start")
            self.post_payment_credit_notes_amount = api_response.get("post_payment_credit_notes_amount")
            self.pre_payment_credit_notes_amount = api_response.get("pre_payment_credit_notes_amount")
            self.receipt_number = api_response.get("receipt_number")
            self.shipping_cost = api_response.get("shipping_cost")
            self.shipping_details = api_response.get("shipping_details")
            self.starting_balance = api_response.get("starting_balance")
            self.statement_descriptor = api_response.get("statement_descriptor")
            self.status = api_response.get("status")
            self.status_transitions = api_response.get("status_transitions")
            # self.finalized_at = api_response.get("finalized_at")
            # self.marked_uncollectible_at = api_response.get("marked_uncollectible_at")
            # self.paid_at = api_response.get("paid_at")
            # self.voided_at = api_response.get("voided_at")
            self.subtotal = api_response.get("subtotal")
            self.subtotal_excluding_tax = api_response.get("subtotal_excluding_tax")
            self.test_clock = api_response.get("test_clock")
            self.total = api_response.get("total")
            self.total_discount_amounts = api_response.get("total_discount_amounts")
            self.total_excluding_tax = api_response.get("total_excluding_tax")
            self.total_taxes = api_response.get("total_taxes")
            self.transfer_data = api_response.get("transfer_data")
            self.webhooks_delivered_at = api_response.get("webhooks_delivered_at")