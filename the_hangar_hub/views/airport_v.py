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
from the_hangar_hub.models.airport_manager import AirportManager
from base_upload.services import retrieval_service
from base_upload.services import upload_service

log = Log()
env = EnvHelper()


@report_errors()
# @require_authentication()  # ToDo: Maybe not required?
@require_airport()
def welcome(request, airport_identifier):
    """
    An individual airport's landing page
    """
    airport = request.airport

    # Airport Status
    # ==============
    if not airport.is_active():
        return render(request, "the_hangar_hub/error_pages/airport_inactive.html")
    if not airport.is_current():
        message_service.post_error("ToDo: When airport is not current???")
    has_hangars = Hangar.objects.filter(building__airport=airport).count()
    has_billing_data = airport.has_billing_data()

    # User Status
    # ===========
    is_manager = airport_service.manages_this_airport()
    rentals = tenant_s.get_rental_agreements(Auth.current_user())
    is_tenant = bool(rentals)
    on_waitlist = airport.get_waitlist().current_user_position()
    active_applications = application_service.get_active_applications(airport=airport)

    if is_manager and not has_hangars:
        return redirect("airport:manage", airport_identifier)

    return render(
        request, "the_hangar_hub/airport/welcome.html",
        {
            "is_manager": is_manager,
            "is_tenant": is_tenant,
            "on_waitlist": on_waitlist,
            "active_applications": active_applications,
        }
    )


@report_errors()
@require_airport_manager()
def my_airport(request, airport_identifier):

    airport = request.airport

    # If no connected account, create it now
    if not airport.stripe_account:
        stripe_service.create_connected_account(airport)

    # If there is a stripe account, refresh with data from Stripe
    stripe_service.sync_account_data(airport)

    # Check connected account
    onboarding_link = None
    if airport.stripe_account:
        # Onboarding link can be used to manage account after onboarding
        onboarding_link = stripe_service.get_onboarding_link(airport)

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
def my_subscription(request, airport_identifier):

    airport = request.airport
    url = stripe_service.get_customer_portal_session(airport)
    if url:
        return redirect(url)

    message_service.post_error("Unable to create a payment portal session")
    return redirect("airport:manage", airport_identifier)


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

@report_errors()
@require_airport_manager()
def upload_logo(request, airport_identifier):
    airport = request.airport
    uploaded_file = None
    try:
        if request.method == 'POST':
            uploaded_file = upload_service.upload_file(
                request.FILES['logo_file'],
                tag=f"logo",
                foreign_table="Airport", foreign_key=airport.id,
                # specified_filename='airport_logo',
                # parent_directory=f'airports/{airport.identifier}/logo'
            )
            log.info(f"Uploaded File: {uploaded_file}")

        if uploaded_file:
            Auth.audit(
                "C", "AIRPORT",
                f"Uploaded airport logo",
                reference_code="Airport", reference_id=airport.id
            )

            # Update tags for any previous logos for this airport
            for logo in retrieval_service.get_all_files().filter(
                tag="logo", foreign_table="Airport", foreign_key=airport.id
            ).exclude(id=uploaded_file.id):
                logo.tag = "old_logo"
                logo.save()

            return HttpResponse("ok")
    except Exception as ee:
        message_service.post_error(f"Could not update airport data: {ee}")

    return HttpResponseForbidden()


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

    # # Since user did not have an account, an email is needed to invite them
    # if "@" not in invitee:
    #     message_service.post_error("The given user information could not be found. Please enter an email address.")
    #     return HttpResponseForbidden()
    #
    # # Create and send an invitation
    # Invitation.invite_manager(airport, invitee)
    # return render(
    #     request, "the_hangar_hub/airport/infrastructure/_manager_table.html",
    #     {
    #         "airport": airport,
    #         "managers": airport_service.get_managers(airport=airport),
    #         "invitations": airport_service.get_pending_invitations(airport, "MANAGER")
    #     }
    # )

