
from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from base.models.utility.error import Error
from base.services import utility_service, message_service
from base_stripe.services import config_service
from base_stripe.models.connected_account import StripeConnectedAccount
from base_stripe.services.config_service import set_stripe_api_key
import stripe
import json

log = Log()
env = EnvHelper()


"""
    PRODUCT
    - Tracks the most important elements of a Stripe Product
    - Auto-updates via Stripe Webhooks
"""
class StripeProduct(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    deleted = models.BooleanField(default=False, db_index=True)
    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)
    stripe_account = models.ForeignKey(
        "base_stripe.StripeConnectedAccount", on_delete=models.CASCADE,
        related_name="products",
        null=True, blank=True,
        db_index=True
    )

    @property
    def account_id(self):
        return self.stripe_account.stripe_id if self.stripe_account else None

    active = models.BooleanField(db_index=True)
    name = models.CharField(max_length=80, null=True, blank=True)
    description = models.CharField(max_length=80, null=True, blank=True)
    metadata = models.JSONField(default=dict, null=True, blank=True)

    def prices_for_display(self):
        return self.prices.filter(display=True)

    def sync(self):
        """
        Update data from Stripe API
        """
        if self.deleted:
            return False
        try:
            log.info(f"Sync {self} ({self.stripe_id})")
            stripe_data = self.api_data()
            log.debug(stripe_data)
            self.active = stripe_data.get("active")
            self.name = stripe_data.get("name")
            self.description = stripe_data.get("description")
            self.metadata = stripe_data.get("metadata")
            self.save()
            return True
        except Exception as ee:
            Error.record(ee, self.stripe_id)
        return False

    def add_metadata(self, data_dict):
        try:
            metadata = self.api_data().get("metadata") or {}
            metadata.update(data_dict)
            # Make sure the model ID is always included
            metadata.update({"model_id": self.id})
            set_stripe_api_key()
            stripe.Product.modify(
                self.stripe_id,
                metadata=metadata
            )

            self.metadata = metadata
            self.save()
        except Exception as ee:
            Error.record(ee, self.stripe_id)


    def api_data(self, expand=None):
        try:
            config_service.set_stripe_api_key()
            params = {}
            if self.stripe_account:
                params["stripe_account"] = self.account_id
            if expand:
                params["expand"] = expand
            return stripe.Product.retrieve(self.stripe_id, **params)
        except Exception as ee:
            Error.record(ee, self)

    @classmethod
    def ids_start_with(cls):
        return "prod_"

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
                model = cls(stripe_id=stripe_id, stripe_account=StripeConnectedAccount.get(account), active=True)
                model.sync()
                return model
            except Exception as ee:
                Error.record(ee, stripe_id)
        else:
            log.error(f"Not a valid {cls} Stripe ID: {stripe_id}")
        return None

    @classmethod
    def obtain(cls, product_type, account=None, name=None, description=None):
        """
        Get or create a product.
        This product will have variable pricing set when creating checkout sessions.
        """
        config_service.set_stripe_api_key()

        # For specified account, or for HH account
        try:
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
        except Exception as ee:
            Error.unexpected(f"Unable to create product: {product_type}", ee, product_type)
            return None

        # List all products (there should only be 2 - HangarRent and ApplicationFee)
        try:
            if account_instance:
                products = stripe.Product.list(limit=20, stripe_account=account_instance.stripe_id)
            else:
                products = stripe.Product.list(limit=20)

            # Fine the product with specified code
            for product in products.auto_paging_iter():
                if product.metadata.get('product_type') == product_type:
                    return product
        except Exception as ee:
            Error.record(ee)

        # Create product with metadata for lookup
        product = None
        try:
            log.info(f"Create new product: {product_type} for account {account_instance}")
            if account_instance:
                product = stripe.Product.create(
                    name=name or product_type,
                    description=description,
                    metadata={
                        'product_type': product_type
                    },
                    stripe_account=account_instance.stripe_id
                )
            else:
                product = stripe.Product.create(
                    name=name or product_type,
                    description=description,
                    metadata={
                        'product_type': product_type
                    },
                )
        except Exception as ee:
            Error.unexpected("Unable to create Stripe product", ee)

        if product:
            try:
                return cls.objects.create(stripe_id=product.id, stripe_account=account_instance, active=True)
            except Exception as ee:
                Error.unexpected("Unable to create stripe product record", ee)
        return None


"""
    Price
    - Tracks the most important elements of a Stripe Price
    - Auto-updates via Stripe Webhooks
"""
class StripePrice(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    deleted = models.BooleanField(default=False, db_index=True)
    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)
    stripe_account = models.ForeignKey(
        "base_stripe.StripeConnectedAccount",
        on_delete=models.CASCADE, related_name="prices",
        null=True, blank=True,
        db_index=True
    )
    @property
    def account_id(self):
        return self.stripe_account.stripe_id if self.stripe_account else None

    # A price may be active, but not want to be displayed on the subscription form
    # (i.e. Early Adopter keeps low price, but no new customers can select it)
    display = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)
    badge = models.CharField(max_length=20, null=True, blank=True)
    features = models.JSONField(default=list, null=True, blank=True)

    product = models.ForeignKey("base_stripe.StripeProduct", models.CASCADE, related_name="prices", db_index=True)
    active = models.BooleanField(db_index=True)
    nickname = models.CharField(max_length=80, null=True, blank=True)
    metadata = models.JSONField(default=dict, null=True, blank=True)
    recurring = models.JSONField(default=dict, null=True, blank=True)
    type = models.CharField(max_length=12, null=True, blank=True)  # one_time or recurring
    unit_amount = models.IntegerField()

    @property
    def dollar_amount(self):
        return utility_service.convert_to_decimal(self.unit_amount / 100)

    @property
    def trial_days(self):
        if self.recurring:
            return self.recurring.get("trial_period_days") or 0
        return 0

    @property
    def recurrence(self):
        if self.type == "recurring" and self.recurring:
            return self.recurring.get("interval")
        else:
            return "one-time"
    @property
    def recurrence_suffix(self):
        return {
            "month": "/month",
            "year": "/year",
            "one-time": "",
        }.get(self.recurrence)

    def features_json(self):
        return json.dumps(self.features or [], indent=4)

    def sync(self):
        """
        Update data from Stripe API
        """
        if self.deleted:
            return False
        try:
            log.info(f"Sync {self} ({self.stripe_id})")
            stripe_data = self.api_data()
            self.product = StripeProduct.from_stripe_id(stripe_data.get("product"))
            self.active = stripe_data.get("active")
            self.nickname = stripe_data.get("nickname")
            self.recurring = stripe_data.get("recurring")
            self.metadata = stripe_data.get("metadata")
            self.unit_amount = stripe_data.get("unit_amount")
            self.type = stripe_data.get("type")
            self.save()
            return True
        except Exception as ee:
            Error.record(ee, self.stripe_id)
        return False

    def add_metadata(self, data_dict):
        try:
            metadata = self.api_data().get("metadata") or {}
            metadata.update(data_dict)
            # Make sure the model ID is always included
            metadata.update({"model_id": self.id})
            set_stripe_api_key()
            stripe.Price.modify(
                self.stripe_id,
                metadata=metadata
            )

            self.metadata = metadata
            self.save()
        except Exception as ee:
            Error.record(ee, self.stripe_id)

    def set_trial_days(self, num_days):
        try:
            if self.recurring:
                days = int(num_days)
                self.recurring["trial_period_days"] = days
                set_stripe_api_key()
                stripe.Price.modify(
                    self.stripe_id,
                    recurring={"trial_period_days": days}
                )
                self.save()
                return True
            else:
                message_service.post_error("Only recurring prices can have trial periods")
        except ValueError:
            message_service.post_error("Trial period must be a number of days")
        except Exception as ee:
            Error.record(ee, self.stripe_id)
        return False

    def api_data(self, expand=None):
        try:
            config_service.set_stripe_api_key()
            params = {}
            if self.stripe_account:
                params["stripe_account"] = self.account_id
            if expand:
                params["expand"] = expand
            return stripe.Product.retrieve(self.stripe_id, **params)
        except Exception as ee:
            Error.record(ee, self)


    @classmethod
    def ids_start_with(cls):
        return "price_"

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

