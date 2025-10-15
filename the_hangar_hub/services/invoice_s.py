from django.http import HttpResponseForbidden

from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.services import accounts_service, invoice_service
from base_stripe.models.connected_account import StripeConnectedAccount
from base_stripe.models.payment_models import StripeSubscription
from base_stripe.models.payment_models import StripeCustomer
from datetime import datetime, timezone, timedelta
from base.services import date_service, utility_service
from the_hangar_hub.models.rental_models import RentalInvoice
from base_stripe.models.payment_models import StripeInvoice as StripeInvoice
from the_hangar_hub.services.stripe import stripe_creation_svc

log = Log()
env = EnvHelper()

"""
    Rental Invoice: Django model tracking an invoice and its status
    Stripe Invoice: An invoice object in Stripe (https://docs.stripe.com/api/invoices/object)
"""


def get_rental_invoice(invoice, post_error=True):
    """
    Given a model or ID for a RentalInvoice or StripeInvoice, return the RentalInvoice model

    Parameter: invoice
        - RentalInvoice (or ID)
        - StripeInvoice (or ID)
    """
    try:
        if str(invoice).isnumeric():
            rental_invoice = RentalInvoice.get(invoice)
        elif str(invoice).startswith("inv_"):
            rental_invoice = RentalInvoice.objects.get(stripe_invoice__stripe_id=invoice)
        elif type(invoice) is RentalInvoice:
            rental_invoice = invoice
        elif type(invoice) is StripeInvoice:
            rental_invoice = RentalInvoice.objects.get(stripe_invoice__stripe_id=invoice.stripe_id)
        else:
            rental_invoice = None
    except Exception as ee:
        log.warning(f"Unable to locate RentalInvoice from '{invoice}'")
        rental_invoice = None

    if post_error and not rental_invoice:
        message_service.post_error("Could not find specified rental agreement")

    return rental_invoice

def get_tenant_invoices(tenant):
    pass


def create_rental_invoice(
        rental_agreement, period_start, period_end, amount_charged, collection=None, invoice_number=None, send_invoice=False
):
    """
    All rent invoices should have a RentalInvoice representation - even if they are automatically created in Stripe
    """
    if not rental_agreement:
        message_service.post_error("Could not find specified rental agreement")
        return None

    airport = rental_agreement.airport

    if not (period_start and period_end and amount_charged):
        message_service.post_error("Date range and amount charged are required parameters.")
        return False

    period_start_date = date_service.string_to_date(period_start, airport.timezone)
    period_end_date = date_service.string_to_date(period_end, airport.timezone)
    if not (period_start_date and period_end_date):
        message_service.post_error("An invalid date was specified. Please check the given dates.")
        return False

    amount_charged_decimal = utility_service.convert_to_decimal(amount_charged)
    if not amount_charged_decimal:
        log.warning(f"Invalid amount_charged: {amount_charged}")
        message_service.post_error("An invalid rent amount was specified. Please check the amount charged.")
        return False

    try:
        rental_invoice = RentalInvoice.objects.create(
            agreement=rental_agreement,
            stripe_invoice=None,
            period_start_date=period_start_date,
            period_end_date=period_end_date,
            amount_charged=amount_charged_decimal,
            status_code="O",  # Open

            # If not using Stripe for invoicing
            invoice_number=invoice_number,
        )
    except Exception as ee:
        Error.unexpected("Unable to create rental invoice", ee)
        return False

    if collection == "stripe_invoice":
        # Create a one-time Stripe invoice
        if not convert_to_stripe(rental_invoice, send_invoice=send_invoice):
            log.warning("Invoice left in manual collection state")
        return rental_invoice


    else:
        # Airport will collect manually
        return rental_invoice


def cancel_invoice(invoice):
    rental_invoice = get_rental_invoice(invoice)
    if not rental_invoice:
        return False

    # If cannot cancel in Stripe, do not cancel local either
    stripe_issue = False

    # If invoice exists in Stripe, make change to Stripe invoice first
    if rental_invoice.stripe_invoice:
        rental_invoice.stripe_invoice.sync()

        # Draft invoices get deleted rather than cancelled
        if rental_invoice.stripe_invoice.status == "draft":
            if not invoice_service.delete_draft_invoice(rental_invoice.stripe_invoice.stripe_id):
                stripe_issue = True

        elif rental_invoice.stripe_invoice.status == "open":
            if not invoice_service.void_invoice(rental_invoice.stripe_invoice.stripe_id):
                stripe_issue = True

        elif rental_invoice.stripe_invoice.status == "paid":
            message_service.post_error("Cannot void a paid invoice.")
            stripe_issue = True

        else:  # uncollectible or void
            pass

    # If there was an issue canceling the Stripe invoice...
    if stripe_issue:
        message_service.post_error("Cancellation of Stripe invoice failed. Invoice status not changed.")
        return False

    # Cancel local representation of invoice
    rental_invoice.status_code = "X"
    rental_invoice.save()
    message_service.post_success("Invoice has been canceled.")
    return True


def waive_invoice(invoice):
    rental_invoice = get_rental_invoice(invoice)
    if not rental_invoice:
        return False

    stripe_issue = False
    if rental_invoice.stripe_invoice:
        rental_invoice.stripe_invoice.sync()

        # Create a credit note for the remaining amount
        if not invoice_service.apply_credit(
            invoice.stripe_id, invoice.stripe_invoice.amount_remaining, reason="Remaining balance waived."
        ):
            stripe_issue = True

    # If there was an issue canceling the Stripe invoice...
    if stripe_issue:
        message_service.post_error("Unable to waive Stripe invoice. Invoice status not changed.")
        return False

    rental_invoice.status_code = "W"
    rental_invoice.save()
    message_service.post_success("Invoice has been waived.")
    return True


def pay_invoice(invoice, amount_paid=None, payment_method_code=None):
    rental_invoice = get_rental_invoice(invoice)
    if not rental_invoice:
        return False

    # A dollar amount may be specified for partial-payment
    this_payment = 0
    partial_payment = None
    if amount_paid:
        amount_paid = utility_service.convert_to_decimal(amount_paid)
        if not amount_paid:
            message_service.post_error("An invalid payment amount was specified.")
            return False

        # There may be multiple partial payments
        this_payment = amount_paid
        total_payments = invoice.amount_paid + amount_paid

        if total_payments < invoice.amount_charged:
            partial_payment = True
            this_payment = amount_paid
            amount_paid = total_payments

    else:
        partial_payment = False
        amount_paid = invoice.amount_charged
        this_payment = invoice.amount_charged - invoice.amount_paid

    paid_in_full = amount_paid >= invoice.amount_charged

    # If using Stripe
    stripe_issue = False
    if invoice.stripe_invoice:
        if partial_payment:
            if not invoice_service.apply_credit(
                invoice.stripe_invoice.stripe_id, this_payment, reason="Partial out-of-band payment"
            ):
                stripe_issue = True
        else:
            if not invoice_service.mark_invoice_paid(invoice.stripe_invoice.stripe_id):
                stripe_issue = True

    # If there was an issue with the Stripe invoice...
    if stripe_issue:
        message_service.post_error("Unable to record payment on Stripe invoice. Invoice status not changed.")
        return False

    try:
        invoice.amount_paid = amount_paid
        invoice.status_code = "P" if paid_in_full else "O"
        invoice.payment_method_code = payment_method_code or invoice.payment_method_code
        if paid_in_full:
            invoice.date_paid = datetime.now(timezone.utc)
        invoice.save()
    except Exception as ee:
        Error.unexpected("Unable to record payment.", ee)
        return False

    if paid_in_full:
        message_service.post_success("Invoice has been marked as paid.")
    else:
        message_service.post_success("Partial invoice payment has been recorded.")
    return True


def get_paid_through_date(rental_agreement):
    invoices = RentalInvoice.objects.filter(agreement=rental_agreement, status_code__in=["P", "W"])
    return max([x.period_end_date for x in invoices]) if invoices else None


def get_next_collection_start_date(rental_agreement):
    paid_through_date = get_paid_through_date(rental_agreement)
    return paid_through_date + timedelta(days=1) if paid_through_date else rental_agreement.start_date


def cancel_open_invoices(rental_agreement):
    invoices = RentalInvoice.objects.filter(agreement=rental_agreement, status_code__in=["I", "O"])
    paid_through_dates = []
    for invoice in invoices:
        if invoice.amount_paid:
            # Do not cancel an invoice that is partially paid
            message_service.post_error(f"Could not cancel partially-paid invoice: {invoice.period_description}")
            continue
        if not cancel_invoice(invoice):
            message_service.post_error(f"Unable to cancel existing invoice: {invoice.period_description}")


def convert_to_stripe(invoice, send_invoice=False):
    return stripe_creation_svc.stripe_invoice_from_rental_invoice(get_rental_invoice(invoice), send_invoice)


