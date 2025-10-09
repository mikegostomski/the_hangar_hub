from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from base.models import Phone, Address
from django.contrib.auth.models import User
from datetime import datetime, timezone
from base.classes.auth.session import Auth
from base.classes.util.date_helper import DateHelper

log = Log()
env = EnvHelper()


class HangarApplication(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    status_code = models.CharField(max_length=1, default="N")
    status_change_date = models.DateTimeField(auto_now_add=True)
    submission_date = models.DateTimeField(blank=True, null=True)

    airport = models.ForeignKey("the_hangar_hub.Airport", models.CASCADE, related_name="applications", db_index=True)

    user = models.ForeignKey(User, models.CASCADE, related_name="applications", db_index=True)
    def applicant_profile(self):
        return Auth.lookup_user_profile(self.user)

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

    @property
    def aircraft_description(self):
        if self.aircraft_make or self.aircraft_model:
            return f"{self.aircraft_make} {self.aircraft_model}".strip()
        if self.aircraft_type_code:
            return f"{self.aircraft_type} (unknown make/model)"
        return "Unknown aircraft type"

    applicant_notes = models.TextField(verbose_name="Applicant Notes", blank=True, null=True)
    manager_notes_public = models.TextField(verbose_name="Manager Notes", blank=True, null=True)
    manager_notes_private = models.TextField(verbose_name="Internal Notes", blank=True, null=True)

    # Application Fee (optional)
    fee_amount = models.DecimalField(verbose_name="Application Fee", decimal_places=2, max_digits=6, null=True, blank=True)
    fee_status = models.CharField(max_length=1, blank=True, null=True)
    fee_payment_method = models.CharField(max_length=30, blank=True, null=True)
    fee_notes = models.TextField(blank=True, null=True)

    # Waitlist (when status_code == "L")
    wl_group_code = models.CharField(max_length=1, verbose_name="Priority", blank=True, null=True)
    wl_index = models.IntegerField(blank=True, null=True)

    @property
    def email(self):
        return self.preferred_email or self.user.email

    @property
    def wl_sort_string(self):
        sub_date = DateHelper(self.submission_date).timestamp()
        return f"{self.wl_group_code}-{self.wl_index or 'z'}-{sub_date}"

    @property
    def wl_reset_sort_string(self):
        sub_date = DateHelper(self.submission_date).timestamp()
        return f"{self.wl_group_code}-{sub_date}"

    def change_status(self, new_status):
        if self.status_code == new_status:
            log.info(f"Status not changed (was already {self.status_code})")
            return

        Auth.audit(
            "U", "STATUS_CHANGE",
            reference_code="HangarApplication", reference_id=self.id,
            previous_value=self.status_code, new_value=new_status
        )

        # If no longer on the waitlist
        if self.status_code == "L":
            self.wl_group_code = None
            self.wl_index = None

        # If just submitted
        if new_status == "S":
            self.submission_date = datetime.now(timezone.utc)

        # Set the new status
        self.status_code = new_status
        self.status_change_date = datetime.now(timezone.utc)

    @property
    def preferred_phone_id(self):
        return self.preferred_phone.id if self.preferred_phone else None

    @property
    def mailing_address_id(self):
        return self.mailing_address.id if self.mailing_address else None

    @property
    def is_active(self):
        return self.status_code in ["N", "I", "P", "S", "L"]

    @property
    def is_incomplete(self):
        return self.status_code in ["N", "I", "P"]

    @staticmethod
    def status_options():
        return {
            "N": "New",
            "I": "Incomplete",
            "P": "Pending Payment",
            "S": "Submitted",
            "A": "Accepted",
            "R": "Rejected",
            "L": "Waitlisted",
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

    @staticmethod
    def wl_group_options():
        return {
            "A": "Urgent",
            "B": "High Priority",
            "C": "Standard",
            "D": "Low Priority",
        }

    @property
    def wl_group(self):
        return self.wl_group_options().get(self.wl_group_code) or self.wl_group_code

    def select(self):
        env.set_session_variable("selected_application", self.id)

    def deselect(self):
        cu = env.get_session_variable("selected_application")
        if cu == self.id:
            env.set_session_variable("selected_application", None)

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

