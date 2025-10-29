from allauth.core.internal.ratelimit import clear

from the_hangar_hub.models.airport import Airport

from base.fixtures.timezones import timezones

from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse, FileResponse
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
from the_hangar_hub.models.airport_manager import AirportManager
from base_upload.services import retrieval_service
from base_upload.services import upload_service
from the_hangar_hub.services.stripe import stripe_creation_svc
log = Log()
env = EnvHelper()



@report_errors()
@require_airport_manager()
def my_airport(request, airport_identifier):

    airport = request.airport

    # If no connected account, create it now
    if not airport.stripe_account:
        stripe_creation_svc.create_connected_account(airport)

    # Check connected account
    onboarding_link = None
    if airport.stripe_account:
        # Onboarding link can be used to manage account after onboarding
        onboarding_link = airport.stripe_account.onboarding_url(
            reverse("airport:manage", args=[airport.identifier])
        )

    return render(
        request, "the_hangar_hub/airport/infrastructure/airport.html",
        {
            "airport": airport,
            "managers": airport.management.all(),
            "invitations": airport_service.get_pending_invitations(airport, "MANAGER"),
            "timezone_options": timezones,
            "onboarding_link": onboarding_link,
        }
    )



@report_errors()
@require_airport_manager()
def update_airport(request, airport_identifier):
    airport = request.airport
    attribute = request.POST.get("attribute")
    value = request.POST.get("value")

    try:
        if not hasattr(airport, attribute):
            message_service.post_error("Invalid airport attribute")
            return HttpResponseForbidden()

        prev_value = getattr(airport, attribute)
        setattr(airport, attribute, value)
        airport.save()
        message_service.post_success("Airport data updated")

        Auth.audit(
            "U", "AIRPORT",
            f"Updated airport data: {attribute}",
            reference_code="Airport", reference_id=airport.id,
            previous_value=prev_value, new_value=value
        )

        if attribute.startswith("billing_") or attribute == "display_name":
            stripe_service.modify_customer_from_airport(airport)
    except Exception as ee:
        message_service.post_error(f"Could not update airport data: {ee}")

    return HttpResponse("ok")
