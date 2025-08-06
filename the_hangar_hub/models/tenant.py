from django.db import models
from django.contrib.auth.models import User
from base.classes.util.log import Log
from datetime import datetime, timezone
from django.db.models import Q
from the_hangar_hub.services import stripe_service
from base_stripe.services import customer_service
from base_stripe.classes.customer_subscription import CustomerSubscription

log = Log()


class Tenant(models.Model):

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tenants", null=True, blank=True)
    contact = models.ForeignKey('base.Contact', on_delete=models.CASCADE, related_name="tenants", null=True, blank=True)

    @property
    def display_name(self):
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}"
        else:
            return self.contact.display_name

    @property
    def email(self):
        if self.user:
            return self.user.email
        else:
            return self.contact.email

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
    subscription_data = None

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    tenant = models.ForeignKey("the_hangar_hub.Tenant", on_delete=models.CASCADE, related_name="rentals")
    hangar = models.ForeignKey('the_hangar_hub.Hangar', on_delete=models.CASCADE, related_name="rentals")

    stripe_customer_id = models.CharField(max_length=60, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=60, unique=True, null=True, blank=True)

    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    rent = models.DecimalField(max_digits=10, decimal_places=2)
    deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    def get_customer_data(self):
        if self.stripe_customer_id:
            return customer_service.get_customer(self.stripe_customer_id)
        else:
            return None

    def get_subscription_data(self):
        if self.subscription_data is None:
            self.subscription_data = CustomerSubscription(self.stripe_subscription_id)
        return self.subscription_data

    def has_subscription(self):
        return self.stripe_subscription_id and self.stripe_customer_id

    def is_current(self):
        now = datetime.now(timezone.utc)
        return (self.start_date or now) <= now and (self.end_date is None or self.end_date > now)

    def is_past(self):
        now = datetime.now(timezone.utc)
        return self.end_date and self.end_date < now

    def is_future(self):
        now = datetime.now(timezone.utc)
        return self.start_date and self.start_date > now

    def default_collection_start_date(self):
        """
        When creating a subscription for this rental agreement, when should Stripe billing begin?
        """
        now = datetime.now(timezone.utc)
        if not self.start_date:
            return now
        elif self.start_date > now:
            return self.start_date
        else:
            return now

    @classmethod
    def current_rentals(cls):
        now = datetime.now(timezone.utc)
        return cls.objects.filter(
            Q(end_date__gt=now) | Q(end_date__isnull=True)
        ).filter(
            # Null start date assumes rental started before joining this site and date is not known
            Q(start_date__lte=now) | Q(start_date__isnull=True)
        )

    @classmethod
    def get(cls, data):
        try:
            return cls.objects.get(pk=data)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None


