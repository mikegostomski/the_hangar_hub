
from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from base.models.utility.error import Error
from base_stripe.services import config_service
from base.services import message_service, utility_service
from base_stripe.classes.api.invoice import InvoiceAPI as InvoiceAPI
from base.classes.auth.session import Auth
from django.contrib.auth.models import User
from django.utils.functional import SimpleLazyObject
from base_stripe.classes.api.customer import Customer as StripeCustomerAPI
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
class StripeCustomer(models.Model):
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
    metadata = models.JSONField(default=dict, null=True, blank=True)

    default_payment_method = models.CharField(max_length=50, null=True, blank=True)
    default_source = models.CharField(max_length=50, null=True, blank=True)

    @property
    def default_payment(self):
        return self.default_payment_method or self.default_source

    def open_invoices(self):
        return self.customer_invoices.filter(status="open")

    def sync(self):
        """
        Update data from Stripe API
        """
        try:
            log.info(f"Sync {self} ({self.stripe_id})")
            config_service.set_stripe_api_key()
            customer = stripe.Customer.retrieve(self.stripe_id, expand=["invoice_settings.default_payment_method"])
            if customer:
                self.full_name = customer.name
                self.email = customer.email
                self.balance_cents = customer.balance
                self.delinquent = customer.delinquent
                self.invoice_prefix = customer.invoice_prefix
                self.metadata = customer.metadata
                if not self.user:
                    self.user = Auth.lookup_user(self.email)

                inv_settings = customer.get("invoice_settings") or {}
                dpm = inv_settings.get("default_payment_method") or {}
                self.default_source = customer.get("default_source")
                self.default_payment_method = dpm.get("type")

                # Expand upon payment method when possible
                if self.default_payment_method:
                    try:
                        pm_id = dpm.get("id")
                        pm = stripe.Customer.retrieve_payment_method(self.stripe_id, pm_id)
                        payment_type = self.default_payment_method
                        if payment_type == "card":
                            card = pm.get("card")
                            exp = f'exp. {card.get("exp_month")}/{card.get("exp_year")}'
                            self.default_payment_method = f'{card.get("brand")} ****{card.get("last4")} {exp}'
                        elif payment_type == "us_bank_account":
                            acct = pm.get("us_bank_account")
                            self.default_payment_method = f'{acct.get("bank_name")} ****{acct.get("last4")}'
                        elif payment_type == "link":
                            self.default_payment_method = "Managed via Link.com"
                    except Exception as ee:
                        Error.record(ee)

                self.save()
                return True
        except Exception as ee:
            Error.record(ee, self.stripe_id)
        return False

    def add_metadata(self, data_dict):
        try:
            config_service.set_stripe_api_key()
            customer = stripe.Customer.retrieve(self.stripe_id)
            metadata = customer.get("metadata")
            if not metadata:
                metadata = {}
            # Add the given data
            metadata.update(data_dict)
            # Make sure the model ID is always included
            metadata.update({"model_id": self.id})

            stripe.Customer.modify(
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
            return stripe.Customer.retrieve(self.stripe_id)
        except Exception as ee:
            Error.record(ee, self.stripe_id)

    def api_wrapper(self):
        """
        Get data from Stripe API and put in custom class
        """
        data = self.api_data()
        return StripeCustomerAPI(data) if data else None

    @classmethod
    def get(cls, xx):
        try:
            if str(xx).isnumeric():
                return cls.objects.get(pk=xx)
            elif type(xx) in [User, SimpleLazyObject]:
                return cls.objects.get(user=xx)
            elif type(xx) is cls:
                return xx
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
    def get_or_create(cls, full_name=None, email=None, user=None, stripe_id=None, phone=None, address_dict=None, metadata=None):
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

        # If given a Stripe Customer ID
        if stripe_id and str(stripe_id).startswith("cus_"):
            try:
                # Look for existing model
                existing = cls.get(stripe_id)
                if existing:
                    return existing

                # Create model from Stripe data
                log.info(f"Creating new Customer model: {stripe_id}")
                cus = StripeCustomer()
                cus.stripe_id = stripe_id
                cus.sync()
                return cus
            except Exception as ee:
                Error.record(ee, stripe_id)

        # Find or create customer from given user data
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

            # Gather all known (verified) email addresses
            verified_emails = [email]
            user_profile = Auth.lookup_user_profile(user) if user else None
            if user_profile:
                verified_emails.extend(user_profile.emails)
            verified_emails = list(set(verified_emails))

            # Look for existing customer model based on all known (verified) email addresses
            existing = None
            for email_address in verified_emails:
                existing = StripeStripeCustomer.get(email_address)
                if existing:
                    break

            if existing:
                log.info(f"Found existing customer: {existing.stripe_id}")
                existing.sync()
                return existing

            # Look for existing customer record in Stripe based on all known (verified) email addresses
            existing_id = None
            for email_address in verified_emails:
                try:
                    config_service.set_stripe_api_key()
                    result = stripe.Customer.list(email=email_address)
                    if result.data:
                        existing_id = result.data[0].get("id")
                        break
                except Exception as ee:
                    Error.record(ee, email_address)
            if existing_id:
                existing = StripeCustomer.from_stripe_id(existing_id)
                if existing:
                    log.info(f"Found existing customer: {existing.stripe_id}")
                    return existing

            # Create a new Stripe Customer
            try:
                log.info(f"Creating new Stripe customer for {email}")
                set_stripe_api_key()
                stripe_customer = stripe.Customer.create(
                    name=full_name,
                    email=email,
                    metadata=metadata or {}
                )
                # API either succeeds or raises an exception
                stripe_id = stripe_customer.get("id")
                log.info(f"Created new Stripe customer: {stripe_id}")

                # Create and return customer_model
                return StripeCustomer.objects.create(
                    full_name=full_name, email=email, stripe_id=stripe_id, user=user, metadata=metadata or {}
                )

            except Exception as ee:
                Error.unexpected("Unable to create Stripe customer record", ee, email)
                return None


"""
    INVOICE
    - Tracks the most important elements of a Stripe Invoice
    - Auto-updates via Stripe Webhooks
"""
class StripeInvoice(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)
    customer = models.ForeignKey("base_stripe.StripeCustomer", models.CASCADE, related_name="customer_invoices", db_index=True)
    subscription = models.ForeignKey("base_stripe.StripeSubscription", models.CASCADE, related_name="subscription_invoices", null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, db_index=True)
    amount_charged = models.DecimalField(decimal_places=2, max_digits=8, default=0.00)
    amount_remaining = models.DecimalField(decimal_places=2, max_digits=8, default=0.00)
    metadata = models.JSONField(default=dict, null=True, blank=True)

    related_type = models.CharField(max_length=20, null=True, blank=True)
    related_id = models.IntegerField(null=True, blank=True)

    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)

    hosted_invoice_url = models.CharField(max_length=500, null=True, blank=True)
    invoice_pdf = models.CharField(max_length=500, null=True, blank=True)

    def sync(self):
        """
        Update data from Stripe API
        """
        if self.status == "deleted":
            # Nothing to update
            return True
        try:
            log.info(f"Sync {self} ({self.stripe_id})")
            config_service.set_stripe_api_key()
            invoice = stripe.Invoice.retrieve(self.stripe_id, expand=["lines"])
            self.customer = StripeCustomer.get(invoice.customer)
            self.status = invoice.status
            self.amount_charged = utility_service.convert_to_decimal(invoice.total/100)
            self.amount_remaining = utility_service.convert_to_decimal(invoice.amount_remaining/100)
            self.metadata = invoice.metadata
            self.hosted_invoice_url = invoice.hosted_invoice_url
            self.invoice_pdf = invoice.invoice_pdf

            try:
                for line in invoice.get("lines").get("data"):
                    if "period" in line:
                        self.period_start = date_service.string_to_date(line.get('period').get("start"))
                        self.period_end = date_service.string_to_date(line.get('period').get("end"))
                    if not self.subscription:
                        if "parent" in line:
                            sid = line.get('parent').get("subscription_item_details")
                            subscription_id = sid.get("subscription") if sid else None
                            if subscription_id:
                                self.subscription = StripeSubscription.from_stripe_id(subscription_id)
            except Exception as ee:
                log.error(f"Error in ChatGPT-created code: {ee}")

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
            elif type(xx) is cls:
                return xx
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
            # Create a new model representation for this invoice
            inv = StripeInvoice()
            inv.stripe_id = stripe_id
            inv.sync()
            return inv

        except Exception as ee:
            Error.record(ee, stripe_id)
            return None




"""
    SUBSCRIPTION
    - Tracks the most important elements of a Stripe Subscription
    - Auto-updates via Stripe Webhooks
"""
class StripeSubscription(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    customer = models.ForeignKey("base_stripe.StripeCustomer", models.CASCADE, related_name="invoices", db_index=True)
    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)

    # incomplete, incomplete_expired, trialing, active, past_due, canceled, unpaid, or paused.
    status = models.CharField(max_length=20, db_index=True)
    metadata = models.JSONField(default=dict, null=True, blank=True)

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

    @staticmethod
    def active_statuses():
        return ["trialing", "active", "past_due", "unpaid", "paused"]

    @property
    def is_active(self):
        return self.status in self.active_statuses()

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
            log.info(f"Sync {self} ({self.stripe_id})")
            subscription = self.api_data()
            if subscription:
                self.status = subscription.status
                self.metadata = subscription.metadata
                self.customer = StripeCustomer.from_stripe_id(subscription.customer)

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


    def add_metadata(self, data_dict):
        try:
            config_service.set_stripe_api_key()
            subscription = stripe.Subscription.retrieve(self.stripe_id)
            metadata = subscription.get("metadata")
            if not metadata:
                metadata = {}
            # Add the given data
            metadata.update(data_dict)
            # Make sure the model ID is always included
            metadata.update({"model_id": self.id})

            stripe.Subscription.modify(
                self.id,
                metadata=metadata
            )

            self.metadata = metadata
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
            elif type(xx) is cls:
                return xx
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
            sub = StripeSubscription()
            sub.stripe_id = stripe_id
            sub.sync()
            return sub
        except Exception as ee:
            Error.record(ee, stripe_id)
            return None


"""
    CHECKOUT SESSION
    - Tracks the most important elements of a Stripe CheckoutSession
    - Auto-updates via Stripe Webhooks
"""
class StripeCheckoutSession(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    customer = models.ForeignKey("base_stripe.StripeCustomer", models.CASCADE, related_name="checkout_sessions", db_index=True)
    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)

    # open, complete, or expired
    status = models.CharField(max_length=20, db_index=True)
    url = models.CharField(max_length=500)
    metadata = models.JSONField(default=dict, null=True, blank=True)
    expiration_date = models.DateTimeField(null=True, blank=True)

    related_type = models.CharField(max_length=20, null=True, blank=True)
    related_id = models.IntegerField(null=True, blank=True)

    @property
    def is_active(self):
        return self.status == "open"

    @property
    def status_display(self):
        return {
            "open": "Awaiting Checkout",
            "complete": "Complete",
            "expired": "Expired",
        }.get(self.status) or self.status.title()

    def api_data(self):
        """
        Get data from Stripe API
        """
        try:
            config_service.set_stripe_api_key()
            return stripe.checkout.Session.retrieve(self.stripe_id)
        except Exception as ee:
            Error.record(ee, self.stripe_id)

    def sync(self, stripe_data=None):
        """
        Update data from Stripe API

        if Stripe data was just obtained (from creation for example), skip the API call
        """
        try:
            log.info(f"Sync {self} ({self.stripe_id})")
            co = stripe_data or self.api_data()
            if co:
                self.status = co.status
                self.metadata = co.metadata
                self.url = co.url
                self.expiration_date = date_service.string_to_date(co.expires_at) if co.expires_at else None
                self.customer = StripeCustomer.from_stripe_id(co.customer)

                self.save()
        except Exception as ee:
            Error.record(ee, self.stripe_id)

    @classmethod
    def get(cls, xx):
        try:
            if str(xx).isnumeric():
                return cls.objects.get(pk=xx)
            elif type(xx) is cls:
                return xx
            else:
                return cls.objects.get(stripe_id=xx)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None


    @classmethod
    def from_stripe_id(cls, stripe_id, stripe_data=None):
        """
        Get (or create if needed) the CheckoutSession model from a Stripe ID
        """
        try:
            # Check for existing record linked to this Stripe subscription
            return cls.objects.get(stripe_id=stripe_id)
        except cls.DoesNotExist:
            pass

        try:
            co = StripeCheckoutSession()
            co.stripe_id = stripe_id
            co.sync(stripe_data=stripe_data)
            return co
        except Exception as ee:
            Error.record(ee, stripe_id)
            return None




