from django.db import models
from django.contrib.auth.models import User
from base.models.utility.error import Error,Log
from base.classes.auth.session import Auth
from datetime import datetime, timezone, timedelta
from base_stripe.models.payment_models import StripeSubscription
from django.db.models import Q
from base.classes.util.date_helper import DateHelper
from base.services import utility_service

log = Log()


"""
TENANT
"""
class Tenant(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    # There MUST be a contact record for a tenant.
    # A User record also contains a Contact, but it is OK to duplicate the reference to it.
    contact = models.ForeignKey('base.Contact', on_delete=models.CASCADE, related_name="tenants", null=True, blank=True)

    # There may not be a user at time of creation (or potentially ever)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tenants", null=True, blank=True)
    customer = models.ForeignKey("base_stripe.StripeCustomer", on_delete=models.CASCADE, related_name="tenants", null=True, blank=True)

    def get_rental_agreement_series_list(self):
        return list(set([rr.series for rr in self.rentals.all()]))

    @property
    def stripe_customer_id(self):
        return self.customer.stripe_id if self.customer else None

    @property
    def display_name(self):
        return self.contact.display_name

    @property
    def email(self):
        return self.contact.email

    @classmethod
    def get(cls, tenant_data):
        try:
            user = None

            if not tenant_data:
                return None

            if str(tenant_data).isnumeric():
                return cls.objects.get(pk=tenant_data)

            # If given a Tenant object, just return it
            if type(tenant_data) is Tenant:
                return tenant_data

            # If given a RentalAgreement object
            if type(tenant_data) is RentalAgreement:
                return tenant_data.tenant

            # If given a User object
            if Auth.is_user_object(tenant_data):
                try:
                    # Return tenant record tied to user
                    return Tenant.objects.get(user=tenant_data)
                except Tenant.DoesNotExist:
                    user = tenant_data
                    tenant_data = user.email
                    # User may have joined after Tenant record was created, or may have multiple verified emails
                    try:
                        user_profile = Auth.lookup_user_profile(user)
                        for email in user_profile.emails if user_profile else []:
                            try:
                                tenant = Tenant.objects.get(contact__email__iexact=email)
                                if tenant:
                                    tenant.user = user
                                    tenant.save()
                                    if tenant.customer and not tenant.customer.user:
                                        tenant.customer.user = user
                                        tenant.customer.save()
                                    return tenant
                            except:
                                pass  # Not found via this email
                    except Exception as ee:
                        Error.record(ee, tenant_data)

            # If given an email address (or user not associated with a Tenant in previous condition)
            if "@" in str(tenant_data):
                try:
                    tenant = Tenant.objects.get(contact__email__iexact=tenant_data)
                    if user and not tenant.user:
                        tenant.user = user
                        tenant.save()
                    else:
                        Error.record(f"Potential duplicate account for tenant: {tenant} - {tenant.user}/{user}")
                    return tenant
                except Tenant.DoesNotExist:
                    return None

            # If given a Stripe customer ID
            if str(tenant_data).startswith("cus_"):
                try:
                    return Tenant.objects.get(customer__stripe_id=tenant_data)
                except Tenant.DoesNotExist:
                    return None

            # Not sure what other type of data could point to a tenant
            else:
                log.error(f"Cannot lookup Tenant given unknown data: {tenant_data}")

        except Exception as ee:
            Error.record(ee, tenant_data)
            return None


class RentalAgreement(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    # Related objects
    tenant = models.ForeignKey("the_hangar_hub.Tenant", on_delete=models.CASCADE, related_name="rentals")
    hangar = models.ForeignKey('the_hangar_hub.Hangar', on_delete=models.CASCADE, related_name="rentals")
    airport = models.ForeignKey('the_hangar_hub.Airport', on_delete=models.CASCADE, related_name="rentals")

    # For changes to rental agreement, new agreements will be created and grouped into a series
    series = models.CharField(max_length=6, db_index=True)
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

    # Most-recent active Stripe subscription
    stripe_subscription = models.ForeignKey(
        "base_stripe.StripeSubscription", on_delete=models.CASCADE, related_name="rental_agreements", null=True, blank=True
    )
    future_stripe_subscription = models.ForeignKey(
        "base_stripe.StripeSubscription", on_delete=models.CASCADE, related_name="future_rental_agreements", null=True, blank=True
    )

    @property
    def stripe_customer_id(self):
        return self.tenant.stripe_customer_id if self.tenant else None

    @property
    def stripe_subscription_id(self):
        return self.stripe_subscription.stripe_id if self.stripe_subscription else None

    @property
    def stripe_subscription_status(self):
        return self.stripe_subscription.status if self.stripe_subscription else None

    @property
    def stripe_metadata_content(self):
        return f'"rental_agreement": "{self.id}"'

    @property
    def active_subscription(self):
        return self.stripe_subscription.is_active if self.stripe_subscription else None

    def set_new_series(self):
        new = utility_service.generate_verification_code(length=6)
        used = self.tenant.get_rental_agreement_series_list() or []
        tries = 1
        while tries < 10 and new in used:
            new = utility_service.generate_verification_code(length=6)
            tries += 1
        self.series = new

    # Related invoice models
    def invoice_models(self):
        return self.invoices.all()

    def open_invoice_models(self):
        return self.invoices.filter(status_code="O")


    _pay_stats = None
    _last_payment_date = None
    _paid_through_date = None
    def relevant_invoice_models(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        rims = self.invoices.filter(Q(status_code__in=["O", "P", "W"]) | Q(last_updated__gt=recent)).order_by("-period_start_date", "-date_created")
        if rims:
            payment_dates = []
            paid_periods = []
            unpaid_periods = []
            for inv in rims:
                if inv.date_paid:
                    payment_dates.append(inv.date_paid)
                # Paid or Waived
                if inv.status_code in ["P", "W"]:
                    paid_periods.append(inv.period_end_date)
                elif inv.status_code in ["O", "U"]:
                    unpaid_periods.append(inv.period_start_date)
            self._last_payment_date = max(payment_dates) if payment_dates else None
            self._paid_through_date = max(paid_periods) if paid_periods else None
            if unpaid_periods:
                self._paid_through_date = min(unpaid_periods)
        if not self._paid_through_date:
            self._paid_through_date = self.start_date
        self._pay_stats = True
        return rims

    def last_payment_date(self):
        if not self._pay_stats:
            self.relevant_invoice_models()
        return self._last_payment_date

    def paid_through_date(self):
        if not self._pay_stats:
            self.relevant_invoice_models()
        return self._paid_through_date

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
            return StripeSubscription.get(self.stripe_subscription_id)
        return None


    @classmethod
    def present_rental_agreements(cls):
        """
        Query to get PRESENT rentals

        Note: This used to be named current_rentals, but "current" became confusing when payment statuses
        came into play (current, delinquent, etc.)
        """
        now = datetime.now(timezone.utc)
        next_month = now + timedelta(days=30)
        return cls.objects.filter(
            Q(end_date__gt=now) | Q(end_date__isnull=True)
        ).filter(
            # Null start date assumes rental started before joining this site and date is not known
            Q(start_date__lte=now) | Q(start_date__isnull=True)
        )

    @classmethod
    def relevant_rental_agreements(cls):
        """
        Query to get PRESENT and near-FUTURE rentals
        """
        now = datetime.now(timezone.utc)
        next_month = now + timedelta(days=30)
        return cls.objects.filter(
            Q(end_date__gt=now) | Q(end_date__isnull=True)
        ).filter(
            # Null start date assumes rental started before joining this site and date is not known
            Q(start_date__lte=next_month) | Q(start_date__isnull=True)
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
    stripe_invoice = models.ForeignKey("base_stripe.StripeInvoice", on_delete=models.CASCADE, related_name="rental_invoices", null=True, blank=True)
    stripe_subscription = models.ForeignKey("base_stripe.StripeSubscription", on_delete=models.CASCADE, related_name="rental_invoices", null=True, blank=True)

    period_start_date = models.DateTimeField()
    period_end_date = models.DateTimeField()
    amount_charged = models.DecimalField(decimal_places=2, max_digits=8)
    amount_paid = models.DecimalField(decimal_places=2, max_digits=8, default=0.00)
    status_code = models.CharField(max_length=1, default="I", db_index=True)
    payment_method_code = models.CharField(max_length=2, null=True, blank=True)
    date_paid = models.DateTimeField(null=True, blank=True)

    @property
    def period_description(self):
        s = DateHelper(self.period_start_date)
        e = DateHelper(self.period_end_date)
        return f"{s.banner_date()} - {e.banner_date()}"


    # If not using Stripe for invoicing
    invoice_number = models.CharField(max_length=50, null=True, blank=True, db_index=True)

    def sync(self):
        if self.stripe_invoice:
            log.info(f"Sync {self}")
            self.stripe_invoice.sync()
            if self.status_code == "W" and self.stripe_status_code == "P":
                # Stripe marks waived invoices as Paid. Do not update Waived to Paid in local model
                pass
            else:
                self.status_code = self.stripe_status_code
            self.amount_charged = self.stripe_invoice.amount_charged
            self.amount_paid = self.stripe_invoice.amount_charged - self.stripe_invoice.amount_remaining
            self.save()

    @staticmethod
    def status_options():
        return {
            "I": "Draft",
            "O": "Open",
            "P": "Paid",
            "W": "Waived",
            "U": "Uncollectible",
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

    @property
    def is_stripe_invoice(self):
        return self.stripe_invoice_id

    @property
    def stripe_id(self):
        return self.stripe_invoice.stripe_id if self.is_stripe_invoice else None

    def stripe_due_date(self):
        # Due date must be in the future
        now = datetime.now(timezone.utc) + timedelta(minutes=5)
        if self.period_start_date > now:
            return int(self.period_start_date.timestamp())
        else:
            return int(now.timestamp())

    def stripe_status(self):
        if self.stripe_invoice:
            return self.status_options().get(self.stripe_status_code) or self.stripe_status_code
        return None

    @property
    def stripe_status_code(self):
        # Codes come from base_stripe.StripeInvoice
        if self.stripe_invoice:
            return {
                "draft": "I",
                "open": "O",
                "paid": "P",
                "uncollectible": "U",
                "void": "X",
                "deleted": "X",  # (a deleted draft invoice)
            }.get(self.stripe_invoice.status)
        return None

    @classmethod
    def get(cls, data):
        try:
            if str(data).startswith("in_"):
                log.debug(f"GET BY STRIPE_ID: '{data}'")
                return cls.objects.get(stripe_invoice__stripe_id=data)
            else:
                log.debug(f"GET BY MODEL ID: '{data}'")
                return cls.objects.get(pk=data)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None