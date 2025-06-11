from django.db import models
from django.contrib.auth.models import User
from base.classes.util.log import Log
from django.utils import timezone
from zoneinfo import ZoneInfo

log = Log()


class Tenant(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tenants", null=True, blank=True)
    contact = models.ForeignKey('base.Contact', on_delete=models.CASCADE, related_name="tenants", null=True, blank=True)

    @classmethod
    def get(cls, data):
        try:
            return cls.objects.get(pk=data)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

class Rental(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="rentals")
    hangar = models.ForeignKey('the_hangar_hub.Hangar', on_delete=models.CASCADE, related_name="rentals")

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    rent = models.DecimalField(max_digits=10, decimal_places=2)
    deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
