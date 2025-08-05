from django.db import models
from base.classes.util.env_helper import EnvHelper, Log

log = Log()
env = EnvHelper()


class StripeCustomer(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)
    email = models.CharField(max_length=180, unique=True, db_index=True)
    user = models.ForeignKey("auth.User", models.CASCADE, related_name="stripe_customers", null=True, blank=True, db_index=True)

    full_name = models.CharField(max_length=150)

    balance_cents = models.IntegerField(default=0)
    delinquent = models.BooleanField(default=False)
    invoice_prefix = models.CharField(max_length=10, null=True, blank=True)

    @classmethod
    def get(cls, xx):
        try:
            if str(xx).isnumeric():
                return cls.objects.get(pk=xx)
            elif "@" in str(xx):
                return cls.objects.get(email__iexact=xx)
            else:
                return cls.objects.get(stripe_id=xx)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None