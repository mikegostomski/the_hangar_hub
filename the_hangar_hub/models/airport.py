from django.db import models
from django.utils import timezone as django_timezone
from zoneinfo import ZoneInfo
from django.urls import reverse
from base_stripe.models import StripeSubscription, StripeInvoice
from the_hangar_hub.models.infrastructure_models import Hangar
from the_hangar_hub.models.application import HangarApplication
from the_hangar_hub.classes.waitlist import Waitlist
from base_upload.services import retrieval_service
from the_hangar_hub.services import stripe_service
from base.models.utility.error import Error, Log, EnvHelper
from decimal import Decimal
from datetime import datetime, timezone
from base.services import date_service
from django.db.models.signals import post_delete
from django.dispatch import receiver
from base_upload.services import retrieval_service
import os

log = Log()
env = EnvHelper()

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


    application_fee_amount = models.DecimalField(decimal_places=2, max_digits=6, null=True, blank=True)

    @property
    def has_application_fee(self):
        return bool(self.application_fee_amount)

    @property
    def application_fee_stripe(self):
        if self.has_application_fee:
            return int(self.application_fee_amount * 100)
        else:
            return 0

    # Stripe Customer Data
    stripe_customer = models.ForeignKey("base_stripe.StripeCustomer", on_delete=models.CASCADE, related_name="subscribers", null=True, blank=True)
    stripe_account = models.ForeignKey("base_stripe.StripeConnectedAccount", on_delete=models.CASCADE, related_name="airports", null=True, blank=True)
    stripe_subscription = models.ForeignKey("base_stripe.StripeSubscription", on_delete=models.CASCADE, related_name="airports", null=True, blank=True)

    stripe_tx_fee = models.DecimalField(decimal_places=4, max_digits=5, null=False, blank=False, default=0.01)
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

    def latest_invoice(self):
        if self.stripe_subscription:
            try:
                return StripeInvoice.objects.filter(subscription=self.stripe_subscription).latest('date_created')
            except StripeInvoice.DoesNotExist:
                pass
        return None

    def subscriptions(self):
        """HangarHub Subscriptions"""
        subs = stripe_service.get_airport_subscriptions(self)
        sub_datas = []
        for sub_data in subs.data:
            # If not yet linked to a subscription, link to first active subscription
            if sub_data.status in ["trialing", "active"] and not self.stripe_subscription:
                sub_model = StripeSubscription.from_stripe_id(sub_data.id)
                if sub_model:
                    self.stripe_subscription = sub_model
                    self.save()

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
            django_timezone.activate(ZoneInfo(self.timezone))
        else:
            django_timezone.deactivate()

    @property
    def tz(self):
        return ZoneInfo(self.timezone or "UTC")

    def today(self):
        """Get today based on airport's local time"""
        now = datetime.now(timezone.utc)
        local_now = now.astimezone(self.tz)
        return (local_now.replace(hour=0, minute=0, second=0, microsecond=0)).astimezone(ZoneInfo("UTC"))

    def end_of_today(self):
        """Get end-of-today based on airport's local time"""
        now = datetime.now(timezone.utc)
        local_now = now.astimezone(self.tz)
        return local_now.replace(hour=23, minute=59, second=59).astimezone(ZoneInfo("UTC"))

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

    def get_new_mx_requests(self):
        return self.maintenance_requests.filter(status_code="R")

    def get_unreviewed_applications(self):
        return self.applications.filter(status_code="S")

    def get_waitlist(self):
        return Waitlist(self)

    def application_preferences(self):
        try:
            return self.application_prefs
        except HangarApplicationPreferences.DoesNotExist:
            return HangarApplicationPreferences.objects.create(airport=self)

    def get_logo(self):
        try:
            return retrieval_service.get_all_files().get(tag="logo", foreign_table="Airport", foreign_key=self.id)
        except:
            return None

    def logo_url(self):
        return f"{env.absolute_root_url}{reverse('airport:logo', args=[self.identifier])}"

    @classmethod
    def get(cls, id_or_ident):
        log.trace([id_or_ident])
        try:
            if str(id_or_ident).isnumeric():
                return cls.objects.get(pk=id_or_ident)
            else:
                return cls.objects.get(identifier__iexact=id_or_ident)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get airport: {ee}")
            return None

    def __str__(self):
        return f"Airport: {self.identifier} ({self.id})"

    def __repr__(self):
        return f"Airport: {self.identifier} ({self.id})"


class CustomizedContent(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    airport = models.OneToOneField("the_hangar_hub.Airport", models.CASCADE, related_name="customized_content", db_index=True, unique=True)

    contact_address = models.TextField(blank=True, null=True)
    frequencies = models.TextField(blank=True, null=True)

    contact_phone = models.CharField(max_length=200, blank=True, null=True)
    contact_email = models.CharField(max_length=200, blank=True, null=True)

    hours_m = models.CharField(max_length=25, blank=True, null=True)
    hours_t = models.CharField(max_length=25, blank=True, null=True)
    hours_w = models.CharField(max_length=25, blank=True, null=True)
    hours_r = models.CharField(max_length=25, blank=True, null=True)
    hours_f = models.CharField(max_length=25, blank=True, null=True)
    hours_s = models.CharField(max_length=25, blank=True, null=True)
    hours_u = models.CharField(max_length=25, blank=True, null=True)
    after_hours = models.TextField(blank=True, null=True)

    avgas_price = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    jeta_price = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    mogas_price = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    logo = models.ImageField(upload_to='airport_logos/', blank=True, null=True)
    url = models.CharField(max_length=256, blank=True, null=True)

    def amenities(self):
        return sorted(
            [x.amenity for x in self.airport.amenities.filter(amenity__approved=True)],
            key=lambda x: x.sort_val
        )

    def amenity_ids(self):
        return [x.amenity.id for x in self.airport.amenities.all()]

    # Calculated fields
    # Number of hangars
    # Number of tie-downs
    # Wait List?

class Amenity(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    sort_modifier = models.CharField(max_length=10)  # Allows grouping things like 100LL and JetA as "gas"
    title = models.CharField(max_length=80, null=True, blank=True)
    icon = models.CharField(max_length=30, null=True, blank=True)
    approved = models.BooleanField(default=False)
    proposed_by_user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, related_name="suggested_amenities", null=True, blank=True)
    proposed_by_airport = models.ForeignKey("the_hangar_hub.Airport", on_delete=models.SET_NULL, related_name="suggested_amenities", null=True, blank=True)

    @property
    def sort_val(self):
        """
        When displaying on screen, update the sorting to include the sort_modifier
        """
        if self.sort_modifier:
            return f"{self.sort_modifier}{self.title}"
        return self.title

    class Meta:
        ordering = ['title']

    @classmethod
    def get(cls, pk):
        log.trace([pk])
        try:
            return cls.objects.get(pk=pk)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None


class Amenities(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    airport = models.ForeignKey("the_hangar_hub.Airport", on_delete=models.CASCADE, related_name="amenities")
    amenity = models.ForeignKey("the_hangar_hub.Amenity", on_delete=models.CASCADE, related_name="airports")


    class Meta:
        ordering = ['amenity__title']

    @classmethod
    def get(cls, airport, amenity):
        log.trace([airport, amenity])
        try:
            return cls.objects.get(airport=airport, amenity=amenity)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

def blog_image_upload_to(instance, filename):
    # Get the file extension
    base, ext = os.path.splitext(filename)
    return f'uploads/airports/blog/{instance.airport.identifier}-{instance.id}{ext}'

class BlogEntry(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    airport = models.ForeignKey("the_hangar_hub.Airport", on_delete=models.CASCADE, related_name="blog_entries")
    title = models.CharField(max_length=250)
    content = models.TextField()

    def files(self):
        return retrieval_service.get_file_query().filter(
            tag=f"blog:{self.airport.id}", foreign_table="BlogEntry", foreign_key=self.id
        )

    def main_image(self):
        for file in self.files():
            if "image" in file.content_type:
                return file
        return None

    @classmethod
    def get(cls, pk):
        try:
            return cls.objects.get(pk=pk)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

# Delete the file from storage when the BlogEntry is deleted
@receiver(post_delete, sender=BlogEntry)
def delete_blog_image_on_delete(sender, instance, **kwargs):
    if instance.image:
        storage = instance.image.storage
        if storage.exists(instance.image.name):
            storage.delete(instance.image.name)

class HangarApplicationPreferences(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    airport = models.OneToOneField("the_hangar_hub.Airport", models.CASCADE, related_name="application_prefs", db_index=True, unique=True)

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
