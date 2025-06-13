from django.db import models
from base.classes.util.log import Log
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.hangar import Hangar
from django.contrib.auth.models import User

log = Log()


class HangarApplication(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    status_code = models.CharField(max_length=1, default="N")
    status_change_date = models.DateTimeField(auto_now_add=True)

    airport = models.ForeignKey(Airport, models.CASCADE, related_name="applications", db_index=True)
    user = models.ForeignKey(User, models.CASCADE, related_name="applications", db_index=True)

    hangar_type_code = models.CharField(max_length=1, default="F")

    # Aircraft Data (optional because an applicant may be in the market for a plane)
    aircraft_make = models.CharField(max_length=30, blank=True, null=True)
    aircraft_model = models.CharField(max_length=30, blank=True, null=True)
    aircraft_wingspan = models.IntegerField(blank=True, null=True)
    aircraft_height = models.IntegerField(blank=True, null=True)
    registration_number = models.CharField(max_length=10, blank=True, null=True)
    plane_notes = models.TextField(blank=True, null=True)

    # Application Fee (optional)
    fee_amount = models.DecimalField(decimal_places=2, max_digits=6, null=True, blank=True)
    fee_status = models.CharField(max_length=1, blank=True, null=True)
    fee_payment_method = models.CharField(max_length=30, blank=True, null=True)
    fee_notes = models.TextField(blank=True, null=True)

    @staticmethod
    def status_options():
        return {
            "N": "New",
            "R": "Reviewed",
            "A": "Accepted",
            "D": "Denied",
            "W": "Withdrawn",
        }

    @staticmethod
    def hangar_type_options():
        return {
            "F": "First Available",
            "T": "T-Hangar",
        }

    @property
    def status(self):
        return self.status_options().get(self.status_code)

    @property
    def hangar_type(self):
        return self.hangar_type_options().get(self.hangar_type_code)

    @classmethod
    def get(cls, ii):
        try:
            return cls.objects.get(pk=ii)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None


class HangarOffer(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    hangar = models.ForeignKey(Hangar, models.CASCADE, related_name="offers", db_index=True)

    status_code = models.CharField(max_length=1, default="A")
    status_change_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    @staticmethod
    def status_options():
        return {
            "N": "New",
            "A": "Accepted",
            "D": "Declined",
            "W": "Withdrawn",
        }

    @property
    def status(self):
        return self.status_options().get(self.status_code)

    @classmethod
    def get(cls, ii):
        try:
            return cls.objects.get(pk=ii)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None
