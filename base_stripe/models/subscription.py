from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from base.models.utility.error import Error
from base_stripe.services import config_service
from base_stripe.models.customer import Customer
import stripe

log = Log()
env = EnvHelper()


class Subscription(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    customer = models.ForeignKey("base_stripe.Customer", models.CASCADE, related_name="invoices", db_index=True)
    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)

    # incomplete, incomplete_expired, trialing, active, past_due, canceled, unpaid, or paused.
    status = models.CharField(max_length=20, db_index=True)

    related_type = models.CharField(max_length=20, null=True, blank=True)
    related_id = models.IntegerField(null=True, blank=True)

    def sync(self):
        """
        Update data from Stripe API
        """
        try:
            config_service.set_stripe_api_key()
            subscription = stripe.Subscription.retrieve(self.stripe_id)
            if subscription:
                self.status = subscription.status
                # if not self.customer:
                log.debug(f"#### Find customer: {subscription.customer}")
                self.customer = Customer.get(subscription.customer)
                log.debug(f"#### Found customer: {self.customer}")
                self.save()
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
