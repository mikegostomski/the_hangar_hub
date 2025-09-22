from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service, utility_service
from base_stripe.models import Customer, Invoice
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.classes.api.invoice import Invoice as InvoiceAPI
from datetime import datetime, timezone, timedelta

log = Log()
env = EnvHelper()


def find_invoices(customer, limit=10):
    """
    Find invoices created in stripe that did not get caught by a webhook
    """
    try:
        customer_model = Customer.get(customer)
        if customer_model:
            log.trace([customer_model, customer_model.stripe_id])
            set_stripe_api_key()
            invoices = stripe.Invoice.list(
                customer=customer_model.stripe_id,
                limit=limit,
            )
            if invoices:
                ids = [x.id for x in invoices.data]
                models = Invoice.objects.filter(stripe_id__in=ids)
                model_ids = [x.stripe_id for x in models] if models else []
                for stripe_id in ids:
                    if stripe_id not in model_ids:
                        inv = Invoice.from_stripe_id(stripe_id)
                        log.info(f"Found stripe invoice {stripe_id}. Created {inv}")
    except Exception as ee:
        Error.unexpected("Could not find customer invoices", ee, customer)







# ToDo: Eventually use only the Invoice model
def get_customer_invoices(customer_id, status="open", since_days=None):
    if since_days:
        since_date = datetime.now(timezone.utc) - timedelta(days=since_days)
        since = int(since_date.timestamp())
    else:
        since = None

    try:
        set_stripe_api_key()
        invoices = stripe.Invoice.list(
            customer=customer_id,
            status=status,
            created={"gte": since} if since else None,
        )
        return [InvoiceAPI(ii) for ii in invoices]
    except Exception as ee:
        Error.unexpected("Could not retrieve customer invoices", ee, customer_id)



def delete_draft_invoice(invoice_id):
    log.trace([invoice_id])
    try:
        set_stripe_api_key()
        stripe.Invoice.delete(invoice_id)
        return True
    except Exception as ee:
        Error.unexpected("Unable to delete draft invoice", ee)
        return False


def void_invoice(invoice_id):
    log.trace([invoice_id])
    try:
        set_stripe_api_key()
        stripe.Invoice.void_invoice(invoice_id)
        return True
    except Exception as ee:
        Error.unexpected("Unable to void invoice", ee)
        return False


def finalize_invoice(invoice_id):
    log.trace([invoice_id])
    try:
        set_stripe_api_key()
        stripe.Invoice.finalize_invoice(invoice_id)
        return True
    except Exception as ee:
        Error.unexpected("Unable to finalize invoice", ee)
        return False

def apply_credit(invoice_id, dollar_amount, reason=None):
    log.trace([invoice_id, dollar_amount, reason])
    try:
        set_stripe_api_key()
        stripe.CreditNote.create(
            invoice=invoice_id,
            amount=int(dollar_amount*100),
            memo=reason
        )
        return True
    except Exception as ee:
        Error.unexpected("Unable to apply credit to invoice", ee)
        return False

def mark_invoice_paid(invoice_id):
    log.trace([invoice_id])
    try:
        set_stripe_api_key()
        stripe.Invoice.pay(invoice_id, paid_out_of_band=True)
        return True
    except Exception as ee:
        Error.unexpected("Unable to mark invoice as paid", ee)
        return False