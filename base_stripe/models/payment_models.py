from decimal import Decimal

from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from base.models.utility.error import Error
from base_stripe.services import config_service
from base.services import message_service, utility_service
from base_stripe.classes.api.invoice import Invoice as InvoiceAPI
from base.classes.auth.session import Auth
from django.contrib.auth.models import User
from django.utils.functional import SimpleLazyObject
from base_stripe.classes.api.customer import Customer as StripeCustomer
import stripe
from base_stripe.services.config_service import set_stripe_api_key
from base.services import date_service, message_service

log = Log()
env = EnvHelper()


"""
    CUSTOMER
    - Tracks the most important elements of a Stripe Customer
    - Auto-updates via Stripe Webhooks
"""
class Customer(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)
    email = models.CharField(max_length=180, unique=True, db_index=True)
    user = models.ForeignKey("auth.User", models.CASCADE, related_name="stripe_customer", null=True, blank=True, db_index=True)
    full_name = models.CharField(max_length=150)

    use_auto_pay = models.BooleanField(default=False)  # ToDo: Probably not used
    balance_cents = models.IntegerField(default=0)
    delinquent = models.BooleanField(default=False)
    invoice_prefix = models.CharField(max_length=10, null=True, blank=True)
    status = models.CharField(max_length=10, null=True, blank=True)
    metadata = models.CharField(max_length=500, null=True, blank=True)

    def open_invoices(self):
        return self.customer_invoices.filter(status="open")

    def sync(self):
        """
        Update data from Stripe API
        """
        try:
            config_service.set_stripe_api_key()
            customer = stripe.Customer.retrieve(self.stripe_id)
            if customer:
                self.full_name = customer.name
                self.email = customer.email
                self.balance_cents = customer.balance
                self.delinquent = customer.delinquent
                self.invoice_prefix = customer.invoice_prefix
                self.metadata = customer.metadata
                if not self.user:
                    self.user = Auth.lookup_user(self.email)
                self.save()
                return True
        except Exception as ee:
            Error.record(ee, self.stripe_id)
        return False

    def api_data(self):
        """
        Get data from Stripe API
        """
        try:
            config_service.set_stripe_api_key()
            return stripe.Customer.retrieve(self.stripe_id)
        except Exception as ee:
            Error.record(ee, self.stripe_id)

    def api_wrapper(self):
        """
        Get data from Stripe API and put in custom class
        """
        data = self.api_data()
        return StripeCustomer(data) if data else None

    @classmethod
    def get(cls, xx):
        try:
            if str(xx).isnumeric():
                return cls.objects.get(pk=xx)
            elif type(xx) in [User, SimpleLazyObject]:
                return cls.objects.get(user=xx)
            elif "@" in str(xx):
                return cls.objects.get(email__iexact=xx)
            else:
                return cls.objects.get(stripe_id=xx)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

    @classmethod
    def from_stripe_id(cls, stripe_id):
        """
        Get (or create if needed) the Customer model from a Stripe ID
        """
        return cls.get_or_create(stripe_id=stripe_id)

    @classmethod
    def get_or_create(cls, full_name=None, email=None, user=None, stripe_id=None):
        """
        Create (if DNE) a Customer record in Stripe, and a local record that ties the Stripe ID to a User/email

        Parameters:
            Must provide one of:
             - full_name AND email, or
             - a user object, or
             - a Stripe customer ID

        Returns local record representing the Stripe customer (customer_model)
        """
        log.trace([full_name, email, user, stripe_id])

        if stripe_id and str(stripe_id).startswith("cus_"):
            try:
                existing = cls.get(stripe_id)
                if existing:
                    return existing

                log.info(f"Creating new Customer model: {stripe_id}")
                config_service.set_stripe_api_key()
                customer = stripe.Customer.retrieve(stripe_id)
                return cls.objects.create(
                    stripe_id=stripe_id,
                    full_name=customer.name,
                    email=customer.email,
                    balance_cents=customer.balance,
                    delinquent=customer.delinquent,
                    invoice_prefix=customer.invoice_prefix,
                    metadata=customer.metadata,
                    user=Auth.lookup_user(customer.email) if not user else user
                )
            except Exception as ee:
                Error.record(ee, stripe_id)

        else:
            user_profile = Auth.lookup_user_profile(user) if user else None
            if user_profile is None and not (full_name and email):
                message_service.post_error(
                    "Full name and email address must be provided to create a Customer record in Stripe"
                )
                return None

            if not full_name:
                full_name = user_profile.display_name
            if not email:
                email = user_profile.email

            # If user was not provided, look for one via email address
            if not user_profile:
                user_profile = Auth.lookup_user_profile(email)
                if user_profile.is_user:
                    user = user_profile.user

            # Look for existing customer record
            existing = None
            if user:
                # Look for ANY verified email address for this user
                user_profile = Auth.lookup_user_profile(user)
                if user_profile:
                    for email_address in user_profile.emails:
                        existing = Customer.get(email_address)
                        if existing:
                            break
            if not existing:
                existing = Customer.get(email)

            if existing:
                # ToDo: Sync data with Stripe data?
                log.info(f"Found existing customer: {existing.stripe_id}")
                return existing

            # Create a new Stripe Customer
            try:
                log.info(f"Creating new Stripe customer for {email}")
                set_stripe_api_key()
                stripe_customer = stripe.Customer.create(
                    name=full_name,
                    email=email,
                )
                # API either succeeds or raises an exception
                stripe_id = stripe_customer.get("id")
                log.info(f"Created new Stripe customer: {stripe_id}")

                # Create and return customer_model
                return Customer.objects.create(
                    full_name=full_name, email=email, stripe_id=stripe_id, user=user
                )

            except Exception as ee:
                Error.unexpected("Unable to create Stripe customer record", ee, email)
                return None


"""
    INVOICE
    - Tracks the most important elements of a Stripe Invoice
    - Auto-updates via Stripe Webhooks
"""
class Invoice(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)
    customer = models.ForeignKey("base_stripe.Customer", models.CASCADE, related_name="customer_invoices", db_index=True)
    subscription = models.ForeignKey("base_stripe.Subscription", models.CASCADE, related_name="subscription_invoices", null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, db_index=True)
    amount_charged = models.DecimalField(decimal_places=2, max_digits=8, default=0.00)
    amount_remaining = models.DecimalField(decimal_places=2, max_digits=8, default=0.00)
    metadata = models.CharField(max_length=500, null=True, blank=True)

    related_type = models.CharField(max_length=20, null=True, blank=True)
    related_id = models.IntegerField(null=True, blank=True)

    due_date = models.DateTimeField(null=True, blank=True)

    def sync(self):
        """
        Update data from Stripe API
        """
        if self.status == "deleted":
            # Nothing to update
            return True
        try:
            config_service.set_stripe_api_key()
            invoice = InvoiceAPI(stripe.Invoice.retrieve(self.stripe_id))
            if invoice:
                self.customer = Customer.get(invoice.customer)
                self.status = invoice.status
                self.amount_charged = utility_service.convert_to_decimal(invoice.total/100)
                self.amount_remaining = utility_service.convert_to_decimal(invoice.amount_remaining/100)
                self.metadata = invoice.metadata
                self.save()
                return True
        except Exception as ee:
            Error.record(ee, self.stripe_id)
        return False

    def add_metadata(self, data_dict):
        try:
            config_service.set_stripe_api_key()
            invoice = stripe.Invoice.retrieve(self.stripe_id)
            metadata = invoice.get("metadata")
            if not metadata:
                metadata = {}
            # Add the given data
            metadata.update(data_dict)
            # Make sure the model ID is always included
            metadata.update({"model_id": self.id})

            stripe.Invoice.modify(
                self.id,
                metadata=metadata
            )

            self.metadata = metadata
            self.save()
        except Exception as ee:
            Error.record(ee, self.stripe_id)


    def api_data(self):
        """
        Get data from Stripe API
        """
        try:

            config_service.set_stripe_api_key()
            return stripe.Invoice.retrieve(self.stripe_id)
        except Exception as ee:
            Error.record(ee, self.stripe_id)

    def api_wrapper(self):
        """
        Get data from Stripe API and put in custom class
        """
        data = self.api_data()
        return InvoiceAPI(data) if data else None


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

    @classmethod
    def from_stripe_id(cls, stripe_id):
        """
        Get (or create if needed) the Invoice model from a Stripe ID
        """
        try:
            # Check for existing record linked to this Stripe invoice
            return cls.objects.get(stripe_id=stripe_id)
        except cls.DoesNotExist:
            pass

        try:
            config_service.set_stripe_api_key()
            invoice = stripe.Invoice.retrieve(stripe_id)
            customer = Customer.get_or_create(stripe_id=invoice.get("customer"))
            due_date = invoice.get("due_date")

            # If a model ID was stored in the invoice metadata, retrieve the model that way
            metadata = invoice.get("metadata")
            if metadata and metadata.get("model_id"):
                existing_id = metadata.get("model_id")
                if existing_id:
                    existing = cls.get(existing_id)
                    if existing:
                        existing.stripe_id = stripe_id
                        existing.save()
                        return existing
                    else:
                        Error.record("Invoice metadata points to non-existing invoice model", metadata.get("model_id"))
                        # Allow to create a new model (?)

            # If tied to a subscription...
            subscription = Subscription.from_stripe_id(invoice.get("subscription")) if invoice.get("subscription") else None

            inv = cls.objects.create(
                customer=customer,
                subscription=subscription,
                stripe_id=stripe_id,
                status=invoice.get("status"),
                due_date=date_service.string_to_date(due_date) if due_date else None,
                metadata=metadata,
            )

        except Exception as ee:
            Error.record(ee, stripe_id)
            return None











"""
    SUBSCRIPTION
    - Tracks the most important elements of a Stripe Subscription
    - Auto-updates via Stripe Webhooks
"""
class Subscription(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    customer = models.ForeignKey("base_stripe.Customer", models.CASCADE, related_name="invoices", db_index=True)
    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)

    # incomplete, incomplete_expired, trialing, active, past_due, canceled, unpaid, or paused.
    status = models.CharField(max_length=20, db_index=True)
    metadata = models.CharField(max_length=500, null=True, blank=True)

    amount = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    start_date = models.DateTimeField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    cancel_at = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=30, null=True, blank=True)


    related_type = models.CharField(max_length=20, null=True, blank=True)
    related_id = models.IntegerField(null=True, blank=True)

    @property
    def is_active(self):
        return self.status in ["trialing", "active", "past_due", "unpaid", "paused"]

    @property
    def status_display(self):
        return {
            "incomplete": "Payment Attempt Failed",
            "incomplete_expired": "Expired - Payment Failed",
            "trialing": "Not Yet Started",
            "active": "Active",
            "past_due": "Past Due",
            "canceled": "Canceled",
            "unpaid": "Unpaid",
            "paused": "Paused",
        }.get(self.status) or self.status.title()

    def api_data(self):
        """
        Get data from Stripe API
        """
        try:
            config_service.set_stripe_api_key()
            return stripe.Subscription.retrieve(self.stripe_id)
        except Exception as ee:
            Error.record(ee, self.stripe_id)

    def sync(self):
        """
        Update data from Stripe API
        """
        try:
            subscription = self.api_data()
            if subscription:
                self.status = subscription.status
                self.metadata = subscription.metadata
                self.customer = Customer.from_stripe_id(subscription.customer)

                self.trial_end_date = date_service.string_to_date(subscription.trial_end)
                self.ended_at = date_service.string_to_date(subscription.ended_at)
                self.cancel_at = date_service.string_to_date(subscription.cancel_at)
                self.cancel_at_period_end = subscription.cancel_at_period_end
                self.canceled_at = date_service.string_to_date(subscription.canceled_at)
                self.cancellation_reason = subscription.cancellation_details.reason

                # Determine recurring charge (sum of items)
                self._populate_recurring_charge(subscription)

                # Determine current period (account for multiple items)
                self._populate_current_period(subscription)

                # Find the date of the first non-zero invoice in this subscription
                self._populate_first_paid_date()

                self.save()
        except Exception as ee:
            Error.record(ee, self.stripe_id)

    def _populate_current_period(self, subscription_data=None):
        if not subscription_data:
            subscription_data = self.api_data()
        period_start = period_end = 0
        for item in subscription_data['items']['data']:
            start = item['current_period_start']
            end = item['current_period_end']
            if end > period_end:
                period_end = end
            if period_start == 0 or start < period_start:
                period_start = start
        self.current_period_start = date_service.string_to_date(period_start)
        self.current_period_end = date_service.string_to_date(period_end)

    def _populate_recurring_charge(self, subscription_data=None):
        if not subscription_data:
            subscription_data = self.api_data()
        recurring_amount = 0
        for item in subscription_data['items']['data']:
            price = item['price']
            amount = price['unit_amount']  # in cents
            quantity = item['quantity']
            recurring_amount = amount * quantity / 100  # Convert to dollars
        self.amount = recurring_amount

    def _populate_first_paid_date(self):
        if not self.start_date:
            invoice_list = stripe.Invoice.list(subscription=self.stripe_id, limit=10)
            for invoice in sorted(invoice_list.auto_paging_iter(), key=lambda i: i['created']):
                if invoice['amount_due'] > 0:
                    self.start_date = date_service.string_to_date(invoice['created'])
                    break


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


    @classmethod
    def from_stripe_id(cls, stripe_id):
        """
        Get (or create if needed) the Subscription model from a Stripe ID
        """
        try:
            # Check for existing record linked to this Stripe subscription
            return cls.objects.get(stripe_id=stripe_id)
        except cls.DoesNotExist:
            pass

        try:
            config_service.set_stripe_api_key()
            subscription = stripe.Subscription.retrieve(stripe_id)
            sub = cls.objects.create(
                customer=Customer.from_stripe_id(subscription.get("customer")),
                stripe_id=stripe_id,
                status=subscription.get("status"),
                metadata=subscription.get("metadata"),
                ended_at=date_service.string_to_date(subscription.ended_at),
                cancel_at=date_service.string_to_date(subscription.cancel_at),
                cancel_at_period_end=subscription.cancel_at_period_end,
                trial_end_date=date_service.string_to_date(subscription.trial_end),
                canceled_at=date_service.string_to_date(subscription.canceled_at),
                cancellation_reason=subscription.cancellation_details.reason,
            )
            sub._populate_recurring_charge(subscription)
            sub._populate_current_period(subscription)
            sub._populate_first_paid_date()
            sub.save()
            return sub
        except Exception as ee:
            Error.record(ee, stripe_id)
            return None







# """
#     SUBSCRIPTION-INVOICE (relation)
#     - Ties an invoice to a subscription
# """
# class SubscriptionInvoice(models.Model):
#     date_created = models.DateTimeField(auto_now_add=True)
#     last_updated = models.DateTimeField(auto_now=True)
#     subscription = models.ForeignKey("base_stripe.Subscription", models.CASCADE, related_name="invoice_relations", db_index=True)
#     invoice = models.ForeignKey("base_stripe.Invoice", models.CASCADE, related_name="subscription_relations", db_index=True)