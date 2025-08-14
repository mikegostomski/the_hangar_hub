from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from django.contrib.auth.models import User
from django.utils.functional import SimpleLazyObject

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