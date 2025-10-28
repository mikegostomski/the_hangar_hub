from django.db import models
from base.classes.util.log import Log
from base.models.utility.error import Error
from base.models.contact.contact import Contact
from base.classes.auth.session import Auth
from the_hangar_hub.models.rental_models import Tenant
from the_hangar_hub.models.application import HangarApplication
from base_stripe.models.payment_models import StripeCustomer

log = Log()


class AirportCustomer(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    airport = models.ForeignKey("the_hangar_hub.Airport", models.CASCADE, related_name="customers", db_index=True)
    contact = models.ForeignKey("base.Contact", models.CASCADE, related_name="customers", db_index=True)
    stripe_customer = models.ForeignKey("base_stripe.StripeCustomer", models.CASCADE, related_name="airport_customers")

    @classmethod
    def get(cls, airport, customer_data):
        existing = None
        if airport and customer_data:
            try:
                if Auth.is_user_object(customer_data):
                    existing = cls.objects.get(airport=airport, contact=customer_data.contact, stripe_customer__deleted=False)
                elif type(customer_data) is Contact:
                    existing = cls.objects.get(airport=airport, contact=customer_data, stripe_customer__deleted=False)
                elif type(customer_data) is Tenant:
                    existing = cls.objects.get(airport=airport, contact=customer_data.contact, stripe_customer__deleted=False)
                elif type(customer_data) is HangarApplication:
                    existing = cls.objects.get(airport=airport, contact=customer_data.user.contact, stripe_customer__deleted=False)
                elif str(customer_data).startswith("cus_"):
                    existing = cls.objects.get(airport=airport, stripe_customer__stripe_id=customer_data, stripe_customer__deleted=False)
                elif "@" in str(customer_data):
                    existing = cls.objects.get(airport=airport, contact=customer_data.contact, stripe_customer__deleted=False)
                else:
                    log.error(f"Unknown type of customer data was given: {customer_data}")
                    # Will not be able to create customer data without sufficient data
                    return None
            except cls.DoesNotExist:
                pass
            except Exception as ee:
                Error.unexpected("Unable to get Stripe customer record", ee, customer_data)
                return None

        if existing:
            return existing

        try:
            if Auth.is_user_object(customer_data):
                contact = customer_data.contact
                user = customer_data
            elif type(customer_data) is Contact:
                contact = customer_data
                user = contact.user
            elif type(customer_data) is Tenant:
                contact = customer_data.contact
                user = customer_data.user
            elif type(customer_data) is HangarApplication:
                contact = customer_data.user.contact
                user = customer_data.user
            else:
                Error.unexpected(
                    "Cannot create Stripe customer without Contact info",
                    f"{customer_data} is not Contact", airport
                )
                return None

            stripe_customer = StripeCustomer.obtain(
                contact=contact, user=user,
                account=airport.stripe_account,
                metadata={"airport": airport.identifier}
            )
            if stripe_customer:
                return cls.objects.create(
                    airport=airport,
                    contact=contact,
                    stripe_customer=stripe_customer
                )

            else:
                log.error("Stripe customer was not created")
                return None
        except Exception as ee:
            Error.unexpected("Unable to create Stripe customer record", ee, customer_data)
            return None
