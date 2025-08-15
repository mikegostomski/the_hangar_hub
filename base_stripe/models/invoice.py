from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from base.models.utility.error import Error
from base_stripe.services import config_service
from base_stripe.classes.api.invoice import Invoice as InvoiceAPI
from base_stripe.models.subscription import Subscription
from base_stripe.models.customer import Customer
import stripe

log = Log()
env = EnvHelper()


class Invoice(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    customer = models.ForeignKey("base_stripe.Customer", models.CASCADE, related_name="customer_invoices", db_index=True)
    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)
    status = models.CharField(max_length=20, db_index=True)

    related_type = models.CharField(max_length=20, null=True, blank=True)
    related_id = models.IntegerField(null=True, blank=True)

    due_date = models.DateTimeField(null=True, blank=True)

    def sync(self):
        """
        Update data from Stripe API
        """
        try:
            config_service.set_stripe_api_key()
            invoice = InvoiceAPI(stripe.Invoice.retrieve(self.stripe_id))
            if invoice:
                self.customer = Customer.get(invoice.customer)
                self.status = invoice.status
                self.save()
                for sub_id in invoice.subscription_ids:
                    try:
                        log.debug(f"#### subscription_relations: {self.subscription_relations.all()}")
                        self.subscription_relations.get(invoice=self, subscription__stripe_id=sub_id)
                    except:
                        subscription = Subscription.get(sub_id)
                        if subscription:
                            SubscriptionInvoice.objects.create(invoice=self, subscription=subscription)

        except Exception as ee:
            Error.record(ee, self.stripe_id)

    @classmethod
    def get(cls, xx):
        try:
            if str(xx).isnumeric():
                return cls.objects.get(pk=xx)
            else:
                return cls.objects.get(stripe_id=xx)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None


class SubscriptionInvoice(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    subscription = models.ForeignKey("base_stripe.Subscription", models.CASCADE, related_name="invoice_relations", db_index=True)
    invoice = models.ForeignKey("base_stripe.Invoice", models.CASCADE, related_name="subscription_relations", db_index=True)