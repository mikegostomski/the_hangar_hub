from django.db import models
from base.models.utility.error import EnvHelper, Log, Error
import stripe
from base_stripe.services.config_service import set_stripe_api_key

log = Log()
env = EnvHelper()

"""
Every object created in stripe must be created for a specified connected account unless it
is created on the primary account.

Every API call must include the connected account's ID
"""

class StripeConnectedAccount(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    stripe_id = models.CharField(max_length=60, db_index=True)
    deleted = models.BooleanField(default=False, db_index=True)

    name = models.CharField(max_length=80, null=True, blank=True)
    charges_enabled = models.BooleanField(default=False)
    transfers_enabled = models.BooleanField(default=False)
    payouts_enabled = models.BooleanField(default=False)
    card_payments_enabled = models.BooleanField(default=False)
    onboarding_complete = models.BooleanField(default=False)

    def onboarding_url(self, return_url, refresh_url=None):
        """
        Link to Stripe session for onboarding, as well as making account changes after onboarding
        """
        try:
            abs_url = env.absolute_root_url
            if return_url and not return_url.startswith(abs_url):
                return_url = f"{abs_url}{return_url}"
            if refresh_url and not refresh_url.startswith(abs_url):
                refresh_url = f"{abs_url}{refresh_url}"

            set_stripe_api_key()
            link = stripe.AccountLink.create(
                account=self.stripe_id,
                type="account_onboarding",
                collection_options={"fields": "eventually_due", "future_requirements": "include"},
                return_url=return_url,
                refresh_url=refresh_url or return_url,
            )
            return link.url
        except Exception as ee:
            Error.unexpected("Unable to create onboarding link to Stripe", ee)
        return None

    def api_data(self, expand=None):
        try:
            set_stripe_api_key()
            params = {}
            if expand:
                params["expand"] = expand
            return self.stripe_api().retrieve(self.stripe_id, **params)
        except Exception as ee:
            Error.record(ee, self)

    def sync(self, api_data=None):
        """
        Sync local (model) data with Stripe (API) data
        """
        try:
            if self.deleted:
                # Cannot sync a deleted object
                return False

            if not api_data:
                api_data = self.api_data()

            if api_data.get("deleted"):
                self.deleted = True
            else:
                self.name = api_data.get("business_profile").get("name")
                self.charges_enabled = api_data.get("charges_enabled")
                self.payouts_enabled = api_data.get("payouts_enabled")
                self.onboarding_complete = api_data.get("details_submitted")
                capabilities = api_data.get("capabilities")
                if capabilities:
                    self.card_payments_enabled = capabilities.get("card_payments") == "active"
                    self.transfers_enabled = capabilities.get("transfers") == "active"
            self.save()
            return True
        except Exception as ee:
            Error.record(ee)
        return False

    @classmethod
    def ids_start_with(cls):
        return "acct_"

    @classmethod
    def stripe_api(cls):
        return stripe.Account

    @classmethod
    def get(cls, xx):
        try:
            if xx is None:
                return None
            elif type(xx) is cls:
                return xx
            elif str(xx).isnumeric():
                return cls.objects.get(pk=xx)
            elif str(xx).startswith(cls.ids_start_with()):
                return cls.objects.get(stripe_id=xx)
            else:
                Error.record(f"{xx} is not a valid way to look up a {cls}")
                return None
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None

    @classmethod
    def from_stripe_id(cls, stripe_id):
        """
        Get (or create if needed) the StripeConnectedAccount model from a Stripe ID
        """
        try:
            # Check for existing record linked to this Stripe invoice
            return cls.objects.get(stripe_id=stripe_id)
        except cls.DoesNotExist:
            pass

        try:
            # Create a new model representation for this StripeConnectedAccount
            model = cls.objects.create(stripe_id=stripe_id)
            model.sync()
            return model
        except Exception as ee:
            Error.record(ee, stripe_id)
            return None

    @classmethod
    def create(cls, **kwargs):
        try:
            set_stripe_api_key()
            api_data = cls.stripe_api().create(**kwargs)
        except Exception as ee:
            Error.unexpected(f"Could not create {cls}", ee, **kwargs)
            return None

        try:
            model = cls.objects.create(stripe_id=api_data.id)
            model.sync(api_data)
            return model
        except Exception as ee:
            Error.unexpected(f"Could not create {cls}", ee, api_data.id)
            return None