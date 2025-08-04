from django.db import models
from base.classes.util.env_helper import EnvHelper, Log

log = Log()
env = EnvHelper()


class ConnectedAccount(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    stripe_id = models.CharField(max_length=60, db_index=True)
    name = models.CharField(max_length=80)

    charges_enabled = models.BooleanField(default=False)
    transfers_enabled = models.BooleanField(default=False)
    payouts_enabled = models.BooleanField(default=False)
    card_payments_enabled = models.BooleanField(default=False)
    onboarding_complete = models.BooleanField(default=False)


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