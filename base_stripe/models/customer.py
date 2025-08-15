from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from base.classes.auth.session import Auth
from django.contrib.auth.models import User
from django.utils.functional import SimpleLazyObject
from base.models.utility.error import Error
from base_stripe.services import config_service
import stripe

log = Log()
env = EnvHelper()


class Customer(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)
    email = models.CharField(max_length=180, unique=True, db_index=True)
    user = models.ForeignKey("auth.User", models.CASCADE, related_name="stripe_customer", null=True, blank=True, db_index=True)

    full_name = models.CharField(max_length=150)

    use_auto_pay = models.BooleanField(default=False)

    balance_cents = models.IntegerField(default=0)
    delinquent = models.BooleanField(default=False)
    invoice_prefix = models.CharField(max_length=10, null=True, blank=True)

    def open_invoices(self):
        return self.invoices.filter(status="open")

    def sync(self):
        """
        Update data from Stripe API
        """
        try:
            config_service.set_stripe_api_key()
            customer = stripe.Customer.retrieve(self.stripe_id)
            if customer:
                self.full_name = customer.name
                self.email = customer.email
                self.balance_cents = customer.balance
                self.delinquent = customer.delinquent
                self.invoice_prefix = customer.invoice_prefix
                if not self.user:
                    self.user = Auth.lookup_user(self.email)
                self.save()
        except Exception as ee:
            Error.record(ee, self.stripe_id)

    @classmethod
    def get(cls, xx):
        try:
            if str(xx).isnumeric():
                return cls.objects.get(pk=xx)
            elif type(xx) in [User, SimpleLazyObject]:
                return cls.objects.get(user=xx)
            elif "@" in str(xx):
                return cls.objects.get(email__iexact=xx)
            else:
                return cls.objects.get(stripe_id=xx)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None