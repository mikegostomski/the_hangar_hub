from base.models.utility.error import EnvHelper, Log, Error
import stripe
from base_stripe.models import StripeCustomer, StripeInvoice
from base_stripe.services.config_service import set_stripe_api_key

log = Log()
env = EnvHelper()


def find_invoices(customer, limit=10):
    """
    Find invoices created in stripe that did not get caught by a webhook
    """
    try:
        customer_model = StripeCustomer.get(customer)
        if customer_model:
            log.trace([customer_model, customer_model.stripe_id])
            stripe_account = customer_model.stripe_account
            set_stripe_api_key()
            invoices = stripe.Invoice.list(
                customer=customer_model.stripe_id,
                stripe_account=stripe_account.stripe_id,
                limit=limit,
            )
            if invoices:
                ids = [x.id for x in invoices.data]
                models = StripeInvoice.objects.filter(stripe_id__in=ids)
                model_ids = [x.stripe_id for x in models] if models else []
                for stripe_id in ids:
                    if stripe_id not in model_ids:
                        inv = StripeInvoice.from_stripe_id(stripe_id, stripe_account)
                        log.info(f"Found stripe invoice {stripe_id}. Created {inv}")
    except Exception as ee:
        Error.unexpected("Could not find customer invoices", ee, customer)









def delete_draft_invoice(invoice_model):
    log.trace([invoice_model])
    try:
        set_stripe_api_key()
        stripe.Invoice.delete(invoice_model.stripe_id, stripe_account=invoice_model.account_id)
        return True
    except Exception as ee:
        Error.unexpected("Unable to delete draft invoice", ee)
        return False


def void_invoice(invoice_model):
    log.trace([invoice_model])
    try:
        set_stripe_api_key()
        stripe.Invoice.void_invoice(invoice_model.stripe_id, stripe_account=invoice_model.account_id)
        return True
    except Exception as ee:
        Error.unexpected("Unable to void invoice", ee)
        return False


def finalize_invoice(invoice_model):
    log.trace([invoice_model])
    try:
        set_stripe_api_key()
        stripe.Invoice.finalize_invoice(invoice_model.stripe_id, stripe_account=invoice_model.account_id)
        return True
    except Exception as ee:
        Error.unexpected("Unable to finalize invoice", ee)
        return False

def apply_credit(invoice_model, credit_amount, reason=None):
    log.trace([invoice_model, credit_amount, reason])
    try:
        set_stripe_api_key()
        stripe.CreditNote.create(
            invoice=invoice_model.stripe_id,
            amount=int(credit_amount*100),
            stripe_account=invoice_model.account_id,
            memo=reason
        )
        return True
    except Exception as ee:
        Error.unexpected("Unable to apply credit to invoice", ee)
        return False

def mark_invoice_paid(invoice_model):
    log.trace([invoice_model])
    try:
        set_stripe_api_key()
        stripe.Invoice.pay(invoice_model.stripe_id, paid_out_of_band=True, stripe_account=invoice_model.account_id)
        return True
    except Exception as ee:
        Error.unexpected("Unable to mark invoice as paid", ee)
        return False