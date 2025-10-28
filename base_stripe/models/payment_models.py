
from django.db import models

from base.classes.util.env_helper import EnvHelper, Log
from base.models.utility.error import Error
from base_stripe.services import config_service
from base.services import utility_service
from base.classes.auth.session import Auth
import stripe
from base_stripe.services.config_service import set_stripe_api_key
from base.services import date_service
from base.classes.util.date_helper import DateHelper
from base_stripe.models.connected_account import StripeConnectedAccount

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
    deleted = models.BooleanField(default=False, db_index=True)

    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)
    email = models.CharField(max_length=180, db_index=True)
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

    # Customers belong to connected accounts, or the HH account
    stripe_account = models.ForeignKey(
        "base_stripe.StripeConnectedAccount",
        on_delete=models.CASCADE, related_name="customers",
        null=True, blank=True,
        db_index=True
    )
    @property
    def account_id(self):
        return self.stripe_account.stripe_id if self.stripe_account else None

    @property
    def credit_balance(self):
        return self.balance_cents/100

    @property
    def default_payment(self):
        return self.default_payment_method or self.default_source

    def open_invoices(self):
        return self.customer_invoices.filter(status="open")

    def api_data(self, expand=None):
        try:
            config_service.set_stripe_api_key()
            params = {}
            if self.stripe_account:
                params["stripe_account"] = self.account_id
            if expand:
                params["expand"] = expand
            return stripe.Customer.retrieve(self.stripe_id, **params)
        except Exception as ee:
            Error.record(ee, self)

    def sync(self):
        """
        Update data from Stripe API
        """
        try:
            log.info(f"Sync {self} ({self.stripe_id})")
            customer = self.api_data(expand=["invoice_settings.default_payment_method"])
            log.debug(customer)
            if customer:
                if customer.get("deleted"):
                    self.deleted = True
                else:
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

    @classmethod
    def ids_start_with(cls):
        return "cus_"

    @classmethod
    def get(cls, xx, account=None):
        try:
            if xx is None:
                return None
            elif type(xx) is cls:
                return xx
            elif str(xx).isnumeric():
                return cls.objects.get(pk=xx)
            elif str(xx).startswith(cls.ids_start_with()):
                return cls.from_stripe_id(xx, account)
            else:
                Error.record(f"{xx} is not a valid way to look up a {cls}")
                return None
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

    @classmethod
    def from_stripe_id(cls, stripe_id, account=None):
        """
        Get (or create if needed) a model from a Stripe ID
        """
        if str(stripe_id).startswith(cls.ids_start_with()):
            try:
                # Look for existing model
                existing = cls.get(stripe_id)
                if existing:
                    return existing

                # Create model from Stripe data
                log.info(f"Creating new {cls} model: {stripe_id}; account: {account}")
                model = cls(stripe_id=stripe_id, stripe_account=StripeConnectedAccount.get(account))
                model.sync()
                return model
            except Exception as ee:
                Error.record(ee, stripe_id)
        else:
            log.error(f"Not a valid {cls} Stripe ID: {stripe_id}")
        return None



    @classmethod
    def obtain(
            cls, account=None, contact=None, display_name=None, email=None, metadata=None, stripe_id=None, user=None,
    ):
        """
        Find existing or create new Stripe Customer
        """
        log.trace(locals())

        # If given a Stripe Customer ID
        if stripe_id:
            if str(stripe_id).startswith("cus_"):
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
            else:
                log.error(f"Not a valid Stripe Customer ID: {stripe_id}")
            return None

        # Look for existing via email and/or user (for specified account)
        emails = []
        if contact:
            emails.append(contact.email)
            if not user:
                user = contact.user
        if user:
            profile = Auth.lookup_user_profile(user, False, False)
            if profile and profile.user:
                emails.extend(profile.emails)
        if email:
            emails.append(email)

        # If no emails were found, there is not enough data to go on
        if not emails:
            log.error("Not enough info to obtain a Stripe Customer ID")
            return None

        # Look for Customers with any of the emails
        emails = list(set(emails))
        customers = cls.objects.filter(email__in=emails, deleted=False)

        # If user is specified, require that user
        if user:
            customers = customers.filter(user=user)

        # For specified account, or for HH account
        account_instance = None
        if account:
            if type(account) is StripeConnectedAccount:
                account_instance = account
            elif str(account).startswith("acct_"):
                account_instance = StripeConnectedAccount.from_stripe_id(str(account))
            else:
                account_instance = None

            if not account_instance:
                log.error(f"Invalid Stripe account: {account}")
                return None

            customers = customers.filter(stripe_account=account_instance)
        else:
            customers = customers.filter(stripe_account__isnull=True)

        # Get customers, most-recently-updated first
        customers = customers.order_by("-last_updated")
        num_existing = len(customers)
        if num_existing == 1:
            return customers[0]
        elif num_existing > 1:
            Error.record("TooManyCustomers", emails)
            # Return the newest one. Manual cleanup may be done later
            return customers[0]
        else:
            log.info("No existing customer. Creating new customer.")

        # Create a new Stripe Customer
        primary_email = email
        try:
            if user:
                if not primary_email:
                    primary_email = user.email
                if not display_name:
                    display_name = user.display_name
            if contact:
                if not primary_email:
                    primary_email = contact.email
                if not display_name:
                    display_name = contact.display_name
            if not primary_email:
                # Shouldn't be possible due to prior checking, but just in case
                primary_email = emails[0]

            if not display_name:
                log.error("Unable to create Customer with no display name")
                return None

            set_stripe_api_key()
            if account_instance:
                stripe_customer = stripe.Customer.create(
                    name=display_name,
                    email=primary_email,
                    metadata=metadata or {},
                    stripe_account=account_instance.stripe_id
                )
            else:
                stripe_customer = stripe.Customer.create(
                    name=display_name,
                    email=primary_email,
                    metadata=metadata or {}
                )
            # API either succeeds or raises an exception
            stripe_id = stripe_customer.get("id")
            log.info(f"Created new Stripe customer: {stripe_id}")

            # Create and return customer_model
            return StripeCustomer.objects.create(
                full_name=display_name, email=primary_email,
                stripe_id=stripe_id, stripe_account=account_instance,
                user=user, metadata=metadata or {}
            )

        except Exception as ee:
            Error.unexpected("Unable to create Stripe customer record", ee, primary_email)
            return None


"""
    INVOICE
    - Tracks the most important elements of a Stripe Invoice
    - Auto-updates via Stripe Webhooks
"""
class StripeInvoice(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    deleted = models.BooleanField(default=False, db_index=True)

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

    # Invoices belong to connected accounts, or the HH account
    stripe_account = models.ForeignKey(
        "base_stripe.StripeConnectedAccount",
        on_delete=models.CASCADE, related_name="invoices",
        null=True, blank=True,
        db_index=True
    )
    @property
    def account_id(self):
        return self.stripe_account.stripe_id if self.stripe_account else None

    def api_data(self, expand=None):
        try:
            config_service.set_stripe_api_key()
            params = {}
            if self.stripe_account:
                params["stripe_account"] = self.account_id
            if expand:
                params["expand"] = expand
            return stripe.Invoice.retrieve(self.stripe_id, **params)
        except Exception as ee:
            Error.record(ee, self)

    def sync(self):
        """
        Update data from Stripe API
        """
        if self.status == "deleted":
            # Nothing to update
            return True
        try:
            log.info(f"Sync {self} ({self.stripe_id})")
            invoice = self.api_data(expand=["lines"])
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

    @classmethod
    def ids_start_with(cls):
        return "inv_"

    @classmethod
    def get(cls, xx, account=None):
        try:
            if xx is None:
                return None
            elif type(xx) is cls:
                return xx
            elif str(xx).isnumeric():
                return cls.objects.get(pk=xx)
            elif str(xx).startswith(cls.ids_start_with()):
                return cls.from_stripe_id(xx, account)
            else:
                Error.record(f"{xx} is not a valid way to look up a {cls}")
                return None
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

    @classmethod
    def from_stripe_id(cls, stripe_id, account=None):
        """
        Get (or create if needed) a model from a Stripe ID
        """
        if str(stripe_id).startswith(cls.ids_start_with()):
            try:
                # Look for existing model
                existing = cls.get(stripe_id)
                if existing:
                    return existing

                # Create model from Stripe data
                log.info(f"Creating new {cls} model: {stripe_id}; account: {account}")
                model = cls(stripe_id=stripe_id, stripe_account=StripeConnectedAccount.get(account))
                model.sync()
                return model
            except Exception as ee:
                Error.record(ee, stripe_id)
        else:
            log.error(f"Not a valid {cls} Stripe ID: {stripe_id}")
        return None




"""
    SUBSCRIPTION
    - Tracks the most important elements of a Stripe Subscription
    - Auto-updates via Stripe Webhooks
"""
class StripeSubscription(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    deleted = models.BooleanField(default=False, db_index=True)

    customer = models.ForeignKey("base_stripe.StripeCustomer", models.CASCADE, related_name="invoices", db_index=True)
    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)

    # Subscription belong to connected accounts, or the HH account
    stripe_account = models.ForeignKey(
        "base_stripe.StripeConnectedAccount",
        on_delete=models.CASCADE, related_name="subscriptions",
        null=True, blank=True,
        db_index=True
    )
    @property
    def account_id(self):
        return self.stripe_account.stripe_id if self.stripe_account else None

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
    def danger(self):
        return self.status in [
            "incomplete", "incomplete_expired",
            "past_due", "unpaid",
            "paused", "canceled"
        ]

    @property
    def status_display(self):
        return {
            "incomplete": "Payment Attempt Failed",
            "incomplete_expired": "Expired - Payment Failed",
            "trialing": f"Starting {DateHelper(self.current_period_end).humanize()}",
            "active": "Active",
            "past_due": "Past Due",
            "canceled": "Canceled",
            "unpaid": "Unpaid",
            "paused": "Paused",
        }.get(self.status) or self.status.title()

    def api_data(self, expand=None):
        try:
            config_service.set_stripe_api_key()
            params = {}
            if self.stripe_account:
                params["stripe_account"] = self.account_id
            if expand:
                params["expand"] = expand
            return stripe.Subscription.retrieve(self.stripe_id, **params)
        except Exception as ee:
            Error.record(ee, self)

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
                return True
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
    def ids_start_with(cls):
        return "sub_"

    @classmethod
    def get(cls, xx, account=None):
        try:
            if xx is None:
                return None
            elif type(xx) is cls:
                return xx
            elif str(xx).isnumeric():
                return cls.objects.get(pk=xx)
            elif str(xx).startswith(cls.ids_start_with()):
                return cls.from_stripe_id(xx, account)
            else:
                Error.record(f"{xx} is not a valid way to look up a {cls}")
                return None
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

    @classmethod
    def from_stripe_id(cls, stripe_id, account=None):
        """
        Get (or create if needed) a model from a Stripe ID
        """
        if str(stripe_id).startswith(cls.ids_start_with()):
            try:
                # Look for existing model
                existing = cls.get(stripe_id)
                if existing:
                    return existing

                # Create model from Stripe data
                log.info(f"Creating new {cls} model: {stripe_id}; account: {account}")
                model = cls(stripe_id=stripe_id, stripe_account=StripeConnectedAccount.get(account))
                model.sync()
                return model
            except Exception as ee:
                Error.record(ee, stripe_id)
        else:
            log.error(f"Not a valid {cls} Stripe ID: {stripe_id}")
        return None


"""
    CHECKOUT SESSION
    - Tracks the most important elements of a Stripe CheckoutSession
    - Auto-updates via Stripe Webhooks
"""
class StripeCheckoutSession(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    deleted = models.BooleanField(default=False, db_index=True)

    customer = models.ForeignKey("base_stripe.StripeCustomer", models.CASCADE, related_name="checkout_sessions", db_index=True)
    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)

    # CheckoutSession belong to connected accounts, or the HH account
    stripe_account = models.ForeignKey(
        "base_stripe.StripeConnectedAccount",
        on_delete=models.CASCADE, related_name="checkouts",
        null=True, blank=True,
        db_index=True
    )
    @property
    def account_id(self):
        return self.stripe_account.stripe_id if self.stripe_account else None

    # open, complete, or expired
    status = models.CharField(max_length=20, db_index=True)
    url = models.CharField(max_length=500, null=True, blank=True)
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

    def api_data(self, expand=None):
        try:
            config_service.set_stripe_api_key()
            params = {}
            if self.stripe_account:
                params["stripe_account"] = self.account_id
            if expand:
                params["expand"] = expand
            return stripe.checkout.Session.retrieve(self.stripe_id, **params)
        except Exception as ee:
            Error.record(ee, self)

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
            return True
        except Exception as ee:
            Error.record(ee, self.stripe_id)


    @classmethod
    def ids_start_with(cls):
        return "cs_"

    @classmethod
    def get(cls, xx, account=None):
        try:
            if xx is None:
                return None
            elif type(xx) is cls:
                return xx
            elif str(xx).isnumeric():
                return cls.objects.get(pk=xx)
            elif str(xx).startswith(cls.ids_start_with()):
                return cls.from_stripe_id(xx, account)
            else:
                Error.record(f"{xx} is not a valid way to look up a {cls}")
                return None
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

    @classmethod
    def from_stripe_id(cls, stripe_id, account=None):
        """
        Get (or create if needed) a model from a Stripe ID
        """
        if str(stripe_id).startswith(cls.ids_start_with()):
            try:
                # Look for existing model
                existing = cls.get(stripe_id)
                if existing:
                    return existing

                # Create model from Stripe data
                log.info(f"Creating new {cls} model: {stripe_id}; account: {account}")
                model = cls(stripe_id=stripe_id, stripe_account=StripeConnectedAccount.get(account))
                model.sync()
                return model
            except Exception as ee:
                Error.record(ee, stripe_id)
        else:
            log.error(f"Not a valid {cls} Stripe ID: {stripe_id}")
        return None




