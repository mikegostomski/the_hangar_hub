from allauth.core.internal.ratelimit import clear

from the_hangar_hub.models.airport import Airport

from base.fixtures.timezones import timezones

from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.db.models import Q
import the_hangar_hub.models
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models import Tenant
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.infrastructure_models import Building, Hangar
from the_hangar_hub.models.invitation import Invitation
from base.services import message_service, utility_service, email_service, date_service
from base.decorators import require_authority, require_authentication, report_errors
from the_hangar_hub.services import airport_service, tenant_s, application_service, stripe_service
from decimal import Decimal
from base.classes.breadcrumb import Breadcrumb
from django.contrib.auth.models import User
import re
from datetime import datetime, timezone
from base.models.contact.contact import Contact
from the_hangar_hub.decorators import require_airport, require_airport_manager
import stripe
from base.models.utility.error import Error
from base_stripe.services import checkout_service
from base_stripe.models.payment_models import StripeCustomer, StripeSubscription
from base_stripe.models.events import StripeWebhookEvent

log = Log()
env = EnvHelper()



@report_errors()
@require_authentication()
@require_airport()
def claim_airport(request, airport_identifier):
    airport = request.airport

    # Airport must be inactive
    if airport.is_active():
        return redirect("airport:welcome", airport.identifier)

    # If airport has a city/state but not a billing city/state, update billing to match
    if airport.city and airport.state:
        if not airport.billing_city and airport.billing_state:
            airport.billing_city = airport.city
            airport.billing_state = airport.state
            airport.save()

    prices = stripe_service.get_subscription_prices()


    return render(
        request, "the_hangar_hub/airport/subscription/index.html",
        {
            "is_manager": False,
            "prices": prices,
        }
    )


@report_errors()
@require_authentication()
@require_airport()
def subscriptions(request, airport_identifier):
    is_manager = airport_service.manages_this_airport()
    prices = stripe_service.get_subscription_prices()

    return render(
        request, "the_hangar_hub/airport/subscription/index.html",
        {
            "is_manager": is_manager,
            "prices": prices,
        }
    )


@report_errors()
@require_authentication()
@require_airport()
def subscribe(request, airport_identifier):
    subscription_id = request.POST.get("subscription_id")

    # Make sure billing address/contact info is present
    airport = request.airport
    if not airport.has_billing_data():
        # If data was just submitted
        attrs = ["email", "phone", "street_1", "street_2", "city", "state", "zip"]
        updated = False
        for attr in [f"billing_{x}" for x in attrs]:
            val = request.POST.get(attr)
            if val or updated:
                setattr(airport, attr, val)
                updated = True
        if updated:
            airport.save()

        if not airport.has_billing_data():
            return render(
                request, "the_hangar_hub/airport/subscription/billing_data.html",
                {
                    "subscription_id": subscription_id,
                }
            )

    # Create Stripe customer if needed
    if not airport.stripe_customer:
        if not stripe_service.create_customer_from_airport(airport):
            message_service.post_error("Could not continue with subscription.")
            return redirect("airport:subscriptions", airport.identifier)

    try:
        checkout_session = stripe_service.get_checkout_session_hh_subscription(request.airport, subscription_id)
        if checkout_session:
            env.set_session_variable("stripe_checkout_session_id", checkout_session.id)
            return redirect(checkout_session.url, code=303)
    except Exception as ee:
        Error.unexpected(
            "Unable to complete subscription payment", ee
        )
    return redirect("airport:subscription_failure", airport_identifier)


@report_errors()
@require_authentication()
@require_airport()
def subscription_success(request, airport_identifier):
    airport = request.airport

    # Verify checkout was actually successful
    co_session_id = env.get_session_variable("stripe_checkout_session_id", reset=True)
    success = checkout_service.verify_checkout(co_session_id)

    # If payment was completed, make this user an airport manager
    if success:
        message_service.post_success("You have successfully subscribed to The Hangar Hub!")

        # Attempt to link with newly created subscription
        stripe_subscriptions = StripeSubscription.objects.filter(
            customer=airport.stripe_customer, status__in=["trialing", "active"]
        )
        if stripe_subscriptions:
            if len(stripe_subscriptions) == 1:
                airport.stripe_subscription = stripe_subscriptions[0]
            else:
                for sub in stripe_subscriptions:
                    sub.sync()
                    if sub.status == "trialing":
                        airport.stripe_subscription = sub
                        break
                    elif sub.status == "active":
                        airport.stripe_subscription = sub

        airport.status_code = "A"
        airport.save()
        airport_service.set_airport_manager(airport, Auth.current_user())
        return redirect("airport:manage", airport.identifier)
    else:
        message_service.post_error("Stripe payment session indicates an incomplete or unsuccessful payment.")
        return redirect("airport:subscription_failure", airport_identifier)


@report_errors()
@require_authentication()
@require_airport()
def subscription_failure(request, airport_identifier):
    co_session_id = env.get_session_variable("stripe_checkout_session_id", reset=True)
    co_session = stripe_service.get_session_details(co_session_id) if co_session_id else None

    return render(request, "the_hangar_hub/airport/subscription/failure.html", {"co_session": co_session})
