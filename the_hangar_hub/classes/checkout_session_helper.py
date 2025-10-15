from the_hangar_hub.services.rental import invoice_svc
from base.models.utility.error import Error, Log, EnvHelper
from base.classes.util.date_helper import DateHelper
from datetime import datetime, timezone, timedelta
from base_stripe.models.payment_models import StripeCheckoutSession
from the_hangar_hub.services.stripe import stripe_creation_svc

log = Log()
env = EnvHelper()


class StripeCheckoutSessionHelper:
    rental_agreement = None
    checkout_sessions = None
    checkout_session = None
    expiration_cd = None

    @property
    def airport(self):
        return self.rental_agreement.airport if self.rental_agreement else None

    @property
    def tenant(self):
        return self.rental_agreement.tenant if self.rental_agreement else None

    @property
    def hangar(self):
        return self.rental_agreement.hangar if self.rental_agreement else None

    @property
    def url(self):
        return self.checkout_session.url if self.checkout_session else None

    @property
    def expiration_moment(self):
        if self.checkout_session and self.checkout_session.expiration_date:
            exp_utc = self.checkout_session.expiration_date
            exp_local = exp_utc.astimezone(self.airport.tz)
            if exp_local.hour == 0 and exp_local.minute == 0:
                exp_cd = DateHelper(exp_utc - timedelta(minutes=1))
            else:
                exp_cd = DateHelper(exp_utc - timedelta(seconds=1))
            return exp_cd.datetime_instance
        else:
            return None

    @property
    def expiration_display(self):
        exp_utc = self.expiration_moment
        if exp_utc:
            cd = DateHelper(exp_utc, format_as_timezone=self.airport.timezone)
            return f"{cd.format()} at {cd.time()}"
        else:
            return "No Expiration"


    def __init__(self, rental_agreement):
        log.trace([rental_agreement])
        self.rental_agreement = rental_agreement

        # Look for existing co sessions
        try:
            self.checkout_sessions = StripeCheckoutSession.objects.filter(
                related_type="RentalAgreement",
                related_id=rental_agreement.id,
            ).order_by("-date_created")
        except Exception as ee:
            Error.record(ee, rental_agreement)

        # Get the latest co session (ignore expired sessions after an open/complete session)
        if self.checkout_sessions:
            latest_session = latest_non_expired = None
            for co in self.checkout_sessions:
                if not latest_session:
                    latest_session = co
                if not latest_non_expired:
                    if co.is_active:
                        latest_non_expired = co
                        break
                self.checkout_session = latest_non_expired or latest_session


    @classmethod
    def initiate_checkout_session(cls, rental_agreement):
        if rental_agreement:
            try:
                co = cls(rental_agreement)

                # ToDo: Expire any open co sessions?
                # ToDo: What if there is a completed co session?

                # Cancel any open invoices
                invoice_svc.cancel_open_invoices(rental_agreement)

                # Start subscription after any paid periods (or on agreement start date)
                collection_start_date = invoice_svc.get_next_collection_start_date(rental_agreement)

                # Create checkout session in Stripe
                co.checkout_session = stripe_creation_svc.get_subscription_checkout_session(
                    rental_agreement, collection_start_date
                )

                return co
            except Exception as ee:
                Error.unexpected("Unable to create checkout session", ee, rental_agreement)

        return None