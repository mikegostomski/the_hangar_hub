from django.db import models
from base.models.utility.error import EnvHelper, Log, Error
import stripe
from base_stripe.services.config_service import set_stripe_api_key

log = Log()
env = EnvHelper()

"""
Every object created in stripe must be created for a specified connected account (airport) unless it
is created on the primary account (hangar hub).

Every lookup must include the connected account's ID
"""

class StripeConnectedAccount(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    deleted = models.BooleanField(default=False, db_index=True)

    stripe_id = models.CharField(max_length=60, db_index=True)
    name = models.CharField(max_length=80)

    charges_enabled = models.BooleanField(default=False)
    transfers_enabled = models.BooleanField(default=False)
    payouts_enabled = models.BooleanField(default=False)
    card_payments_enabled = models.BooleanField(default=False)
    onboarding_complete = models.BooleanField(default=False)

    def sync(self):
        try:
            set_stripe_api_key()
            stripe_account = stripe.Account.retrieve(self.stripe_id)
            capabilities = stripe_account.get("capabilities")

            # Sync local data with Stripe data
            self.name = stripe_account.get("business_profile").get("name")
            self.charges_enabled = stripe_account.get("charges_enabled")
            self.payouts_enabled = stripe_account.get("payouts_enabled")
            self.onboarding_complete = stripe_account.get("details_submitted")
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
    def get(cls, xx):
        try:
            if xx is None:
                return None
            elif type(xx) is cls:
                return xx
            elif str(xx).isnumeric():
                return cls.objects.get(pk=xx)
            elif str(xx).startswith(cls.ids_start_with()):
                return cls.from_stripe_id(xx)
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
            ca = StripeConnectedAccount()
            ca.stripe_id = stripe_id
            ca.sync()
            return ca

        except Exception as ee:
            Error.record(ee, stripe_id)
            return None

