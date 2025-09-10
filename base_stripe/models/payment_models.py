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

    use_auto_pay = models.BooleanField(default=False)
    balance_cents = models.IntegerField(default=0)
    delinquent = models.BooleanField(default=False)
    invoice_prefix = models.CharField(max_length=10, null=True, blank=True)
    status = models.CharField(max_length=10, null=True, blank=True)

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

    customer = models.ForeignKey("base_stripe.Customer", models.CASCADE, related_name="customer_invoices", db_index=True)
    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)
    status = models.CharField(max_length=20, db_index=True)
    amount_charged = models.DecimalField(decimal_places=2, max_digits=8, default=0.00)
    amount_remaining = models.DecimalField(decimal_places=2, max_digits=8, default=0.00)

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
                self.save()
                for sub_id in invoice.subscription_ids:
                    try:
                        log.debug(f"#### subscription_relations: {self.subscription_relations.all()}")
                        self.subscription_relations.get(invoice=self, subscription__stripe_id=sub_id)
                    except:
                        subscription = Subscription.get(sub_id)
                        if subscription:
                            SubscriptionInvoice.objects.create(invoice=self, subscription=subscription)
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
    def create_from_stripe(cls, stripe_invoice_id):
        try:
            # Check for existing record linked to this Stripe invoice
            return cls.objects.get(stripe_id=stripe_invoice_id)
        except cls.DoesNotExist:
            pass

        try:
            config_service.set_stripe_api_key()
            invoice = stripe.Invoice.retrieve(stripe_invoice_id)
            customer = Customer.get_or_create(stripe_id=invoice.get("customer"))
            due_date = invoice.get("due_date")

            # If a model ID was stored in the invoice metadata, retrieve the model that way
            metadata = invoice.get("metadata")
            if metadata and metadata.get("model_id"):
                existing_id = metadata.get("model_id")
                if existing_id:
                    existing = cls.get(existing_id)
                    if existing:
                        existing.stripe_id = stripe_invoice_id
                        existing.save()
                        return existing
                    else:
                        Error.record("Invoice metadata points to non-existing invoice model", metadata.get("model_id"))
                        # Allow to create a new model (?)

            return cls.objects.create(
                customer=customer,
                stripe_id=stripe_invoice_id,
                status=invoice.get("status"),
                due_date=date_service.string_to_date(due_date) if due_date else None,
            )
        except Exception as ee:
            Error.record(ee, stripe_invoice_id)
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

    related_type = models.CharField(max_length=20, null=True, blank=True)
    related_id = models.IntegerField(null=True, blank=True)

    def sync(self):
        """
        Update data from Stripe API
        """
        try:
            config_service.set_stripe_api_key()
            subscription = stripe.Subscription.retrieve(self.stripe_id)
            if subscription:
                self.status = subscription.status
                # if not self.customer:
                log.debug(f"#### Find customer: {subscription.customer}")
                self.customer = Customer.get(subscription.customer)
                log.debug(f"#### Found customer: {self.customer}")
                self.save()
        except Exception as ee:
            Error.record(ee, self.stripe_id)

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



"""
    SUBSCRIPTION-INVOICE (relation)
    - Ties an invoice to a subscription
"""
class SubscriptionInvoice(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    subscription = models.ForeignKey("base_stripe.Subscription", models.CASCADE, related_name="invoice_relations", db_index=True)
    invoice = models.ForeignKey("base_stripe.Invoice", models.CASCADE, related_name="subscription_relations", db_index=True)