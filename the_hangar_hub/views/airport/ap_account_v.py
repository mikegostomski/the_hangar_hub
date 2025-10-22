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
def my_subscription(request, airport_identifier):

    airport = request.airport
    url = stripe_service.get_customer_portal_session(airport)
    if url:
        return redirect(url)

    message_service.post_error("Unable to create a payment portal session")
    return redirect("airport:manage", airport_identifier)



@report_errors()
@require_airport_manager()
def add_manager(request, airport_identifier):
    airport = request.airport
    invitee = request.POST.get("invitee")
    log.trace([airport, invitee])

    # Check for existing user
    existing_user = Auth.lookup_user_profile(invitee)
    # If user already has an account, just add them as a manager
    if existing_user:
        if airport_service.set_airport_manager(airport, existing_user):
            message_service.post_success(f"Added airport manager: {invitee}")
        else:
            message_service.post_error(f"Could not add airport manager: {invitee}")
        return render(
            request, "the_hangar_hub/airport/infrastructure/_manager_table.html",
            {
                "airport": airport,
                "managers": airport_service.get_managers(airport=airport),
                "invitations": airport_service.get_pending_invitations(airport, "MANAGER")
            }
        )

    # Since user did not have an account, an email is needed to invite them
    if "@" not in invitee:
        message_service.post_error("The given user information could not be found. Please enter an email address.")
        return HttpResponseForbidden()

    # Create and send an invitation
    Invitation.invite_manager(airport, invitee)
    return render(
        request, "the_hangar_hub/airport/infrastructure/_manager_table.html",
        {
            "airport": airport,
            "managers": airport_service.get_managers(airport=airport),
            "invitations": airport_service.get_pending_invitations(airport, "MANAGER")
        }
    )


@report_errors()
@require_airport_manager()
def update_manager(request, airport_identifier):
    airport = request.airport
    manager_id = request.POST.get("manager_id")
    new_status = request.POST.get("new_status")
    log.trace([airport, manager_id, new_status])

    try:
        # Check for existing user
        mgr = AirportManager.get(manager_id)
        if not mgr:
            message_service.post_error("Specified manager was not found.")
            return HttpResponseForbidden()
        if mgr.airport != airport:
            message_service.post_error("Invalid manager record was specified.")
            return HttpResponseForbidden()
        if new_status not in mgr.status_options():
            message_service.post_error("Invalid manager status was specified.")
            return HttpResponseForbidden()

        old_status = mgr.status
        if old_status != new_status:
            mgr.status_code = new_status
            mgr.status_change_date = datetime.now(timezone.utc)
            mgr.save()

        # An inactive user will cause the manager record to appear inactive
        if new_status == "A" and mgr.status == "I":
            mgr.user.is_active = True
            mgr.user.save()

        Auth.audit(
            "U", "AIRPORT",
            "Updated airport manager status",
            "AirportManager", mgr.id,
            previous_value=old_status, new_value=new_status
        )
    except Exception as ee:
        Error.unexpected(
            "There was an error updating the manager record", ee
        )

    return render(
        request, "the_hangar_hub/airport/infrastructure/_manager_table.html",
        {
            "airport": airport,
            "managers": airport_service.get_managers(airport=airport),
            "invitations": airport_service.get_pending_invitations(airport, "MANAGER")
        }
    )
