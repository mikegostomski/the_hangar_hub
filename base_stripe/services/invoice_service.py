from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service, utility_service
from base_stripe.services.config_service import set_stripe_api_key, get_stripe_address_dict
from base_stripe.classes.api.invoice import Invoice
from datetime import datetime, timezone, timedelta

log = Log()
env = EnvHelper()


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
        return [Invoice(ii) for ii in invoices]
    except Exception as ee:
        Error.unexpected("Could not retrieve customer invoices", ee, customer_id)



# def delete_draft_invoice(invoice_id):
#     log.trace([invoice_id])
#     try:
#         set_stripe_api_key()
#         invoice = stripe.Invoice.void_invoice(invoice_id)
#         return True
#     except Exception as ee:
#         Error.unexpected("Unable to delete invoice", ee)
#         return False