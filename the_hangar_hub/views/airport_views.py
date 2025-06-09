from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from base.classes.util.log import Log
from base.classes.auth.auth import Auth
from base.services.message_service import post_error
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.invitation import Invitation
from base.services import message_service, utility_service, email_service
from base.decorators import require_authority, require_authentication
from the_hangar_hub.services import airport_service
from base.fixtures.timezones import timezones

log = Log()

@require_authentication()
def welcome(request):
    identifier = request.GET.get("identifier")
    matches = None
    if identifier and len(identifier) >= 3:
        # Look for matching airports
        matches = Airport.objects.filter(identifier__icontains=identifier)

    return render(
        request, "the_hangar_hub/airport/welcome.html",
        {
            "identifier": identifier,
            "matches": matches,
        }
    )

@require_authentication()
def select_airport(request):
    airport_id = request.POST.get("airport_id")
    airport = Airport.get(airport_id)
    if not airport:
        message_service.post_error("Airport not found")
        return redirect("hub:welcome")

    # Get existing airport managers (including inactive ones)
    managers = airport_service.get_managers(airport)
    is_manager = is_inactive = False

    # If managers exist, see if this user is already one of them
    if managers:
        for manager in managers:
            if manager.user == request.user:
                is_manager = True
                log.info(f"Is already a manager for {airport.identifier}")
                if manager.status != "A":
                    log.warning(f"Is a non-active manager for {airport.identifier}")
                    is_inactive = True
                elif not manager.user.is_active:
                    log.warning(f"Is a manager, but a non-active user")
                    is_inactive = True
                break

        # Since managers exist for this airport, this user must be an active manager or ask an existing one for access
        if is_inactive or not is_manager:
            if not is_manager:
                message_service.post_error(
                    "This airport already has a manager. You'll need to request access from existing management."
                )
            else:
                message_service.post_error(
                    "Your airport management status is inactive. You'll need to request access from existing management."
                )

            return render(
                request, "the_hangar_hub/airport/access_denied.html",
                {"airport": airport}
            )

    # Since no managers exist for this airport, auto-assign this user to be the manager for this airport
    else:
        log.info(f"No managers exist for {airport}")
        if airport_service.set_airport_manager(airport, request.user):
            message_service.post_success(f"You are now the airport manager for {airport.identifier}")
        else:
            message_service.post_error(f"Unable to record you as the manager for {airport.identifier}")

    return redirect("hub:manage_airport", airport.identifier)


@require_authentication()
def manage_airport(request, airport_identifier):
    airport = Airport.get(airport_identifier)
    if not airport:
        message_service.post_error("The specified airport was not found.")
        return redirect("hub:welcome")

    # User must be an active manager for this airport
    # Page will also list all managers, which is why I'm selecting all of them
    managers = airport_service.get_managers(airport)
    user_profile = Auth().get_user()

    # Is this user an active manager?
    is_manager = bool([mgmt.is_active for mgmt in managers if mgmt.user == user_profile.django_user()])
    if not is_manager:
        message_service.post_error("Only airport managers may manage airport data.")
        return  render(
            request, "the_hangar_hub/airport/access_denied.html",
            {"airport": airport}
        )

    airport.activate_timezone()

    return render(
        request, "the_hangar_hub/airport/manage_airport/manage_airport.html",
        {
            "airport": airport,
            "managers": managers,
            "invitations": airport_service.get_pending_invitations(airport, "MANAGER"),
            "timezone_options": timezones,
        }
    )

@require_authentication()
def update_airport_data(request):
    airport_id = request.POST.get("airport_id")
    attribute = request.POST.get("attribute")
    value = request.POST.get("value")
    airport = Airport.get(airport_id)
    if not airport:
        message_service.post_error("The specified airport was not found.")
        return HttpResponseForbidden()

    # User must be an active manager for this airport
    if not airport_service.is_airport_manager():
        message_service.post_error("Only airport managers may manage airport data.")
        return  HttpResponseForbidden()

    try:
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
    except Exception as ee:
        message_service.post_error(f"Could not update airport data: {ee}")

    return HttpResponse("ok")


@require_authentication()
def add_airport_manager(request):
    airport_id = request.POST.get("airport_id")
    invitee = request.POST.get("invitee")
    log.trace([airport_id, invitee])

    airport = Airport.get(airport_id)
    if not airport:
        message_service.post_error("The specified airport was not found.")
        return HttpResponseForbidden()

    # User must be an active manager for this airport
    if not airport_service.is_airport_manager():
        message_service.post_error("Only airport managers may invite other managers.")
        return  HttpResponseForbidden()

    airport.activate_timezone()

    # Check for existing user
    existing_user = Auth.lookup_user(invitee)
    # If user already has an account, just add them as a manager
    if existing_user:
        if airport_service.set_airport_manager(airport, existing_user):
            message_service.post_success(f"Added airport manager: {invitee}")
        else:
            message_service.post_error(f"Could not add airport manager: {invitee}")
        return render(
            request, "the_hangar_hub/airport/manage_airport/_manager_table.html",
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
    Invitation.invite(airport, invitee, "MANAGER").send()
    return render(
        request, "the_hangar_hub/airport/manage_airport/_manager_table.html",
        {
            "airport": airport,
            "managers": airport_service.get_managers(airport=airport),
            "invitations": airport_service.get_pending_invitations(airport, "MANAGER")
        }
    )


@require_authentication()
def accept_invitation(request, verification_code):
    invite = Invitation.get(verification_code)
    error_html = "the_hangar_hub/airport/invitations/invitation_error.html"

    if not invite:
        message_service.post_error("The specified invitation was not found.")
        return render(request, error_html, {"invite": invite})
    elif invite.is_invalid():
        return render(request, error_html, {"invite": invite})

    user_profile = Auth().get_user()
    if user_profile.email.lower() != invite.email.lower():
        return render(request, error_html, {"invite": invite})




    return HttpResponse("Invalid Invitation...")