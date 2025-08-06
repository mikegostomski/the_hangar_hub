from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service, utility_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict

log = Log()
env = EnvHelper()


def delete_draft_invoice(invoice_id):
    log.trace([invoice_id])
    try:
        set_stripe_api_key()
        invoice = stripe.Invoice.void_invoice(invoice_id)
        return True
    except Exception as ee:
        Error.unexpected("Unable to delete invoice", ee)
        return False