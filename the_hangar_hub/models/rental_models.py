from calendar import month

from django.db import models
from django.contrib.auth.models import User
from base.classes.util.log import Log
from datetime import datetime, timezone, timedelta
from django.db.models import Q
from the_hangar_hub.services import stripe_service
from base_stripe.services import customer_service
from base_stripe.classes.customer_subscription import CustomerSubscription
from base_stripe.models.subscription import Subscription

log = Log()


class Tenant(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    # There MUST be a contact record for a tenant.
    # A User record also contains a Contact, but it is OK to duplicate the reference to it.
    contact = models.ForeignKey('base.Contact', on_delete=models.CASCADE, related_name="tenants", null=True, blank=True)

    # There may not be a user at time of creation (or potentially ever)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tenants", null=True, blank=True)

    stripe_customer_id = models.CharField(max_length=60, null=True, blank=True)

    @property
    def display_name(self):
        return self.contact.display_name

    @property
    def email(self):
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

class RentalAgreement(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    # Related objects
    tenant = models.ForeignKey("the_hangar_hub.Tenant", on_delete=models.CASCADE, related_name="rentals")
    hangar = models.ForeignKey('the_hangar_hub.Hangar', on_delete=models.CASCADE, related_name="rentals")
    airport = models.ForeignKey('the_hangar_hub.Airport', on_delete=models.CASCADE, related_name="rentals")

    # For changes to rental agreement, new agreements will be created
    prior_agreement = models.ForeignKey('the_hangar_hub.RentalAgreement', on_delete=models.CASCADE, null=True, blank=True)
    _next_agreement = None
    def next_agreement(self):
        if not self._next_agreement:
            try:
                self._next_agreement = RentalAgreement.objects.get(prior_agreement=self)
            except:
                return None
        return self._next_agreement

    # Rental agreement terms
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    rent = models.DecimalField(max_digits=10, decimal_places=2)
    deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    # Related invoice models
    def invoice_models(self):
        return self.invoices.all()

    # Most-recent active Stripe subscription
    stripe_subscription_id = models.CharField(max_length=60, unique=True, null=True, blank=True)


    # Past/Present/Future Rental Agreement?
    def is_present(self):
        now = datetime.now(timezone.utc)
        return (self.start_date or now) <= now and (self.end_date is None or self.end_date > now)

    def is_past(self):
        now = datetime.now(timezone.utc)
        return self.end_date and self.end_date < now

    def is_future(self):
        now = datetime.now(timezone.utc)
        return self.start_date and self.start_date > now


    """
    STRIPE DATA
    - Payments and invoicing via Stripe is not a requirement
    - Users have the ability to end their Stripe subscription, in which case they
      would need to make other payment arrangements with the airport (for example,
      cash or check payments)
    """
    subscription_data = None
    def get_subscription_data(self):
        if self.subscription_data is None:
            self.subscription_data = CustomerSubscription(self.stripe_subscription_id)
        return self.subscription_data

    def has_subscription(self):
        return self.stripe_subscription_id

    def default_collection_start_date(self):
        """
        When creating a subscription for this rental agreement, when should Stripe billing begin?
        """
        now = datetime.now(timezone.utc)
        if not self.start_date:
            return now
        elif self.start_date > now:
            return self.start_date
        elif self.start_date.year < now.year or self.start_date.month < now.month:
            try:
                return now.replace(day=self.start_date.day)
            except:
                return now
        else:
            return now

    def default_collection_start_period_end_date(self):
        start = self.default_collection_start_date().replace(hour=0, minute=0, second=0, microsecond=0)
        end_month = start.month + 1
        end_year = start.year
        if end_month == 13:
            end_month = 12
            end_year = start.year + 1
        return start.replace(month=end_month, year=end_year) - timedelta(seconds=1)


    def get_stripe_subscription_model(self):
        """
        Get local representation of stripe subscription
        """
        if self.stripe_subscription_id:
            return Subscription.get(self.stripe_subscription_id)
        return None


    # def get_customer_data(self):
    #     if self.stripe_customer_id:
    #         return customer_service.get_stripe_customer(self.stripe_customer_id)
    #     else:
    #         return None


    @classmethod
    def present_rental_agreements(cls):
        """
        Query to get PRESENT rentals

        Note: This used to be named current_rentals, but "current" became confusing when payment statuses
        came into play (current, delinquent, etc.)
        """
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


class RentalInvoice(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    agreement = models.ForeignKey("the_hangar_hub.RentalAgreement", on_delete=models.CASCADE, related_name="invoices")
    stripe_invoice = models.ForeignKey("base_stripe.Invoice", on_delete=models.CASCADE, related_name="rental_invoices", null=True, blank=True)
    stripe_subscription = models.ForeignKey("base_stripe.Subscription", on_delete=models.CASCADE, related_name="rental_invoices", null=True, blank=True)

    period_start_date = models.DateTimeField()
    period_end_date = models.DateTimeField()
    amount_charged = models.DecimalField(decimal_places=2, max_digits=8)
    amount_paid = models.DecimalField(decimal_places=2, max_digits=8, default=0.00)
    status_code = models.CharField(max_length=1, default="I", db_index=True)
    payment_method_code = models.CharField(max_length=2, null=True, blank=True)
    date_paid = models.DateTimeField(null=True, blank=True)

    # If not using Stripe for invoicing
    invoice_number = models.CharField(max_length=50, null=True, blank=True, db_index=True)

    @staticmethod
    def status_options():
        return {
            "I": "Incomplete",
            "O": "Open",
            "P": "Paid",
            "W": "Waived",
            "X": "Cancelled",
        }

    def status(self):
        return self.status_options().get(self.status_code) or self.status_code

    @staticmethod
    def payment_method_options():
        return {
            "CA": "Cash",
            "CH": "Check",
            "CC": "Credit Card",
            "S": "Stripe",
            "O": "Other",
        }

    def payment_method(self):
        return self.payment_method_options().get(self.payment_method_code) or self.payment_method_code

    @classmethod
    def get(cls, data):
        try:
            return cls.objects.get(pk=data)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None