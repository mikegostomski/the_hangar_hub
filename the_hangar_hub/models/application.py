from django.db import models
from base.classes.util.log import Log
from base.models import Phone, Address
from django.contrib.auth.models import User
from datetime import datetime, timezone
from base.classes.auth.session import Auth

log = Log()


class HangarApplication(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    status_code = models.CharField(max_length=1, default="N")
    status_change_date = models.DateTimeField(auto_now_add=True)
    submission_date = models.DateTimeField(blank=True, null=True)

    airport = models.ForeignKey("the_hangar_hub.Airport", models.CASCADE, related_name="applications", db_index=True)
    user = models.ForeignKey(User, models.CASCADE, related_name="applications", db_index=True)

    preferred_email = models.EmailField(verbose_name="Email Address", blank=True, null=True)
    preferred_phone = models.ForeignKey(Phone, models.CASCADE, verbose_name="Phone Number", related_name="applications", blank=True, null=True)
    mailing_address = models.ForeignKey(Address, models.CASCADE, verbose_name="Address", related_name="applications", blank=True, null=True)

    hangar_type_code = models.CharField(verbose_name="Hangar Type", max_length=1, default="F")
    aircraft_type_code = models.CharField(verbose_name="Aircraft Type", max_length=2, default="A")

    # Aircraft Data (optional because an applicant may be in the market for a plane)
    aircraft_make = models.CharField(verbose_name="Aircraft Make", max_length=30, blank=True, null=True)
    aircraft_model = models.CharField(verbose_name="Aircraft Model", max_length=30, blank=True, null=True)
    aircraft_wingspan = models.IntegerField(verbose_name="Wingspan", blank=True, null=True)
    aircraft_height = models.IntegerField(verbose_name="Height", blank=True, null=True)
    registration_number = models.CharField(verbose_name="Registration Number", max_length=10, blank=True, null=True)
    plane_notes = models.TextField(verbose_name="Notes", blank=True, null=True)

    # Application Fee (optional)
    fee_amount = models.DecimalField(decimal_places=2, max_digits=6, null=True, blank=True)
    fee_status = models.CharField(max_length=1, blank=True, null=True)
    fee_payment_method = models.CharField(max_length=30, blank=True, null=True)
    fee_notes = models.TextField(blank=True, null=True)

    def change_status(self, new_status):
        Auth.audit(
            "U", "STATUS_CHANGE",
            reference_code="HangarApplication", reference_id=self.id,
            previous_value=self.status_code, new_value=new_status
        )
        self.status_code = new_status
        self.status_change_date = datetime.now(timezone.utc)
        if new_status == "S":
            self.submission_date = datetime.now(timezone.utc)

    @property
    def preferred_phone_id(self):
        return self.preferred_phone.id if self.preferred_phone else None

    @property
    def mailing_address_id(self):
        return self.mailing_address.id if self.mailing_address else None

    @property
    def is_active(self):
        return self.status_code in ["N", "I", "S", "R"]

    @property
    def is_incomplete(self):
        return self.status_code in ["N", "I"]

    @staticmethod
    def status_options():
        return {
            "N": "New",
            "I": "Incomplete",
            "S": "Submitted",
            "R": "Reviewed",
            "A": "Accepted",
            "D": "Denied",
            "W": "Withdrawn",
        }

    @property
    def status(self):
        return self.status_options().get(self.status_code)

    @staticmethod
    def hangar_type_options():
        return {
            "F": "First Available",
            "T": "T-Hangar",
        }

    @property
    def hangar_type(self):
        return self.hangar_type_options().get(self.hangar_type_code)

    @staticmethod
    def aircraft_type_options():
        return {
            "AP": "Airplane",
            "RC": "Rotorcraft",
            "GL": "Glider",
            "LA": "Lighter than air",
            "PL": "Powered lift",
            "PP": "Powered parachute",
            "WS": "Weight-shift",
        }

    @property
    def aircraft_type(self):
        return self.aircraft_type_options().get(self.aircraft_type_code) or self.aircraft_type_code


    @classmethod
    def get(cls, ii):
        try:
            return cls.objects.get(pk=ii)
        except cls.DoesNotExist:
            log.debug(f"DID NOT FIND APPLICATION #{ii} ({type(ii)})")
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

    @classmethod
    def start(cls, airport, user):
        # If an incomplete application exists, resume it
        try:
            return cls.objects.get(airport=airport, user=user, status_code="I")
        except cls.DoesNotExist:
            return cls.objects.create(airport=airport, user=user, status_code="I")


class HangarOffer(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    hangar = models.ForeignKey("the_hangar_hub.Hangar", models.CASCADE, related_name="offers", db_index=True)

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

