
from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from base.models.utility.error import Error
from base.services import utility_service, message_service
from base_stripe.services import config_service
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
    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)

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
        try:
            log.info(f"Sync {self} ({self.stripe_id})")
            stripe_data = self.api_data()
            self.active = stripe_data.active
            self.name = stripe_data.name
            self.description = stripe_data.description
            self.metadata = stripe_data.metadata
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

    def api_data(self):
        try:
            config_service.set_stripe_api_key()
            return stripe.Product.retrieve(self.stripe_id)
        except Exception as ee:
            Error.record(ee, self.stripe_id)
            return {}

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
        log.trace([stripe_id])
        if stripe_id:
            try:
                model = cls.get(stripe_id)
                if not model:
                    model = cls()
                    model.stripe_id = stripe_id
                    model.sync()
                return model
            except Exception as ee:
                Error.record(ee, stripe_id)
        return None


"""
    Price
    - Tracks the most important elements of a Stripe Price
    - Auto-updates via Stripe Webhooks
"""
class StripePrice(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    stripe_id = models.CharField(max_length=60, unique=True, db_index=True)

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
        try:
            log.info(f"Sync {self} ({self.stripe_id})")
            stripe_data = self.api_data()
            self.product = StripeProduct.from_stripe_id(stripe_data.product)
            self.active = stripe_data.active
            self.nickname = stripe_data.nickname
            self.recurring = stripe_data.recurring
            self.metadata = stripe_data.metadata
            self.unit_amount = stripe_data.unit_amount
            self.type = stripe_data.type
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

    def api_data(self):
        try:
            config_service.set_stripe_api_key()
            return stripe.Price.retrieve(self.stripe_id)
        except Exception as ee:
            Error.record(ee, self.stripe_id)
            return {}

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
        log.trace([stripe_id])
        if stripe_id:
            try:
                model = cls.get(stripe_id)
                if not model:
                    model = cls()
                    model.stripe_id = stripe_id
                    model.sync()
                return model
            except Exception as ee:
                Error.record(ee, stripe_id)
        return None

