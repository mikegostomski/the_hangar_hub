from django.db import models
from base.classes.util.log import Log
from django.utils import timezone
from zoneinfo import ZoneInfo
from the_hangar_hub.models.hangar import Hangar
from the_hangar_hub.models.application import HangarApplication
from the_hangar_hub.classes.waitlist import Waitlist
from base_upload.services import retrieval_service
from the_hangar_hub.services import stripe_service
from base.models.utility.error import Error
from decimal import Decimal
from base.classes.util.date_helper import DateHelper
from base.services import date_service

log = Log()


class Airport(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    display_name = models.CharField(max_length=200, blank=False, null=False)
    identifier = models.CharField(max_length=6, unique=True, db_index=True)
    city = models.CharField(max_length=60)
    state = models.CharField(max_length=3)
    country = models.CharField(max_length=3, null=True, blank=True)
    timezone = models.CharField(max_length=50, blank=True, null=True)

    # Email displayed to users/tenants who need to contact the airport
    info_email = models.CharField(max_length=150, blank=True, null=True)
    url = models.CharField(max_length=256, blank=True, null=True)

    application_fee_amount = models.DecimalField(decimal_places=2, max_digits=6, null=True, blank=True)

    @property
    def application_fee_stripe(self):
        if self.application_fee_amount:
            return int(self.application_fee_amount * 100)
        else:
            return 0

    # Stripe Customer Data
    stripe_customer_id = models.CharField(max_length=60, blank=True, null=True)
    subscription_id = models.CharField(max_length=60, blank=True, null=True)
    billing_email = models.CharField(max_length=150, blank=True, null=True)
    billing_phone = models.CharField(max_length=10, blank=True, null=True)
    billing_street_1 = models.CharField(max_length=100, blank=True, null=True)
    billing_street_2 = models.CharField(max_length=100, blank=True, null=True)
    billing_city = models.CharField(max_length=60, blank=True, null=True)
    billing_state = models.CharField(max_length=2, blank=True, null=True)
    billing_zip = models.CharField(max_length=12, blank=True, null=True)

    # A referral code is required to claim a new airport
    referral_code = models.CharField(max_length=30, blank=True, null=True, db_index=True)
    status_code = models.CharField(max_length=1, default="I")

    def has_billing_data(self):
        return self.billing_email and self.billing_city and self.billing_state and self.billing_zip

    def is_active(self):
        """
        Has this airport ever been active on The Hangar Hub?
        """
        return self.status_code != "I"  # ToDo: revisit when more statuses exist

    def is_current(self):
        """
        Is this airport active and current (paid-in-full)?
        """
        if not self.is_active():
            return False

        customer_data = stripe_service.get_customer_from_airport(self)
        if not customer_data:
            Error.record(f"Unable to retrieve customer data for active airport: {self}")
            # Customer record was created before activating airport
            # Assume API error and do not consider delinquent
            return True

        # Consider a zero balance to be current
        try:
            if int(customer_data.balance) == 0:
                return True
        except Exception as ee:
            log.error(f"Non-number balance for {self}: {customer_data.balance}")

        # Consider the "delinquent" property the final indicator
        try:
            return not customer_data.delinquent
        except Exception as ee:
            log.error(f"Unable to determine delinquency: {self}")
            return True  # Assume API error?

    def subscriptions(self):
        subs = stripe_service.get_airport_subscriptions(self)
        sub_datas = []
        for sub_data in subs.data:
            latest_invoice = sub_data.latest_invoice

            item_list = sub_data["items"]["data"]
            current_period_start = date_service.string_to_date(item_list[0].current_period_start)
            current_period_end = date_service.string_to_date(item_list[0].current_period_end)
            lookup_keys = [y.lookup_key for y in [x.price for x in item_list]]

            plan_prices = stripe_service.get_subscription_prices()
            cents_due = latest_invoice.amount_due
            cents_paid = latest_invoice.amount_paid
            cents_remaining = latest_invoice.amount_remaining
            effective_at = date_service.string_to_date(latest_invoice.effective_at)
            period_start = date_service.string_to_date(latest_invoice.period_start)
            period_end = date_service.string_to_date(latest_invoice.period_end)

            
            sub_datas.append(
                {
                    # "latest_invoice": sub_data.latest_invoice,
                    # "items": item_list,
                    "lookup_keys": lookup_keys,
                    "amount_due": Decimal(latest_invoice.amount_due/100),
                    "amount_paid": Decimal(latest_invoice.amount_paid/100),
                    "amount_remaining": Decimal(latest_invoice.amount_remaining/100),
                    "effective_at": effective_at,
                    "current_period_start": current_period_start,
                    "current_period_end": current_period_end,
                    "invoice_status": latest_invoice.status,
                    "invoice_pdf": latest_invoice.invoice_pdf,
                    "hosted_invoice_url": latest_invoice.hosted_invoice_url,
                    "subscription_prices": [plan_prices.get(price_id) for price_id in lookup_keys],
                }
            )

        return sub_datas

    def activate_timezone(self):
        if self.timezone:
            timezone.activate(ZoneInfo(self.timezone))
        else:
            timezone.deactivate()

    def get_building(self, building_identifier):
        if str(building_identifier).isnumeric():
            return self.buildings.get(pk=building_identifier)
        else:
            return self.buildings.get(code=building_identifier)

    def get_hangar(self, hangar_identifier):
        try:
            if str(hangar_identifier).isnumeric():
                return Hangar.objects.get(building__airport=self, pk=hangar_identifier)
            else:
                return Hangar.objects.get(building__airport=self, code=hangar_identifier)
        except Hangar.DoesNotExist:
            return None

    def get_unreviewed_applications(self):
        return self.applications.filter(status_code="S")

    def get_waitlist(self):
        return Waitlist(self)

    def application_preferences(self):
        try:
            return self.application_prefs.get()
        except HangarApplicationPreferences.DoesNotExist:
            return HangarApplicationPreferences.objects.create(airport=self)

    def get_logo(self):
        try:
            return retrieval_service.get_all_files().get(tag="logo", foreign_table="Airport", foreign_key=self.id)
        except:
            return None

    @classmethod
    def get(cls, id_or_ident):
        log.trace([id_or_ident])
        try:
            if str(id_or_ident).isnumeric():
                return cls.objects.get(pk=id_or_ident)
            else:
                return cls.objects.get(identifier=id_or_ident)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get airport: {ee}")
            return None

    def __str__(self):
        return f"Airport: {self.identifier} ({self.id})"

    def __repr__(self):
        return f"Airport: {self.identifier} ({self.id})"


class HangarApplicationPreferences(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    airport = models.ForeignKey("the_hangar_hub.Airport", models.CASCADE, related_name="application_prefs", db_index=True, unique=True)

    required_fields_csv = models.TextField(blank=True, null=True)
    ignored_fields_csv = models.TextField(blank=True, null=True)

    infotext_top = models.TextField(blank=True, null=True)
    infotext_personal = models.TextField(blank=True, null=True)
    infotext_aircraft = models.TextField(blank=True, null=True)
    infotext_hangar = models.TextField(blank=True, null=True)
    infotext_bottom = models.TextField(blank=True, null=True)

    @property
    def required_fields(self):
        return self.required_fields_csv.split(",") if self.required_fields_csv else []

    @property
    def ignored_fields(self):
        return self.ignored_fields_csv.split(",") if self.ignored_fields_csv else []

    @property
    def optional_fields(self):
        return [x.name for x in self.fields() if x.name not in self.required_fields and x.name not in self.ignored_fields]

    @staticmethod
    def fields():
        return [
            x for x in HangarApplication._meta.get_fields() if x.name not in [
                # Application fields not displayed on the application
                "id",
                "last_updated", "date_created", "status_change_date", "submission_date",
                "airport", "user",
                "status_code",
                "wl_index", "wl_group_code",
                "manager_notes_public", "manager_notes_private",
            ] and not x.name.startswith("fee")
        ]

    @classmethod
    def get(cls, id_or_airport):
        try:
            if type(id_or_airport) is Airport:
                return cls.objects.get(airport=id_or_airport)
            else:
                return cls.objects.get(pk=id_or_airport)
        except cls.DoesNotExist:
            log.debug(f"Application Preferences not found: {id_or_airport}")
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None
