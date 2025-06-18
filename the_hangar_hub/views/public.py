from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden

from base.classes.breadcrumb import Breadcrumb
from base.classes.util.env_helper import Log, EnvHelper
from base.services import auth_service, message_service
from base.services.message_service import post_error
from the_hangar_hub.decorators import require_airport
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.invitation import Invitation
from the_hangar_hub.services import airport_service, tenant_service
log = Log()
env = EnvHelper()

def home(request):
    Breadcrumb.clear()

    if request.user.is_authenticated:
        # Look for incomplete applications
        log.debug("LOOKING...")
        incomplete_application = tenant_service.get_incomplete_applications()
        incomplete_application = incomplete_application[0] if incomplete_application else None
    else:
        incomplete_application = None


    return render(
        request, "the_hangar_hub/public/home.html",
        {
            "incomplete_application": incomplete_application,
        }
    )


def invitation_landing(request, invitation_code):
    if not invitation_code:
        return redirect("hub:home")

    invite = Invitation.get(invitation_code)
    if not invite:
        message_service.post_error("Invalid invitation code.")
        return redirect("hub:home")

    if invite.status_code == "A":
        # Already accepted. Perhaps using the email as a bookmark to the site?
        return redirect("hub:home")

    elif invite.is_inactive(post_errors=True):
        return redirect("hub:home")

    elif request.user.is_authenticated:
        if not invite.accept():
            message_service.post_error("There ws an error accepting your invitation.")
        return redirect("hub:home")

    # Non-authenticated user has a valid invitation.
    env.set_session_variable("invitation_code", invitation_code)

    return render(
        request, "the_hangar_hub/public/invitation_landing.html",
        {
            "invite": invite,
        }
    )


def search(request):
    log.trace()
    try:
        identifier = request.GET.get("identifier")
        matches = None
        if identifier and len(identifier) >= 3:
            # Look for matching airports
            matches = Airport.objects.filter(identifier__icontains=identifier)

        # If exactly one match, select it
        if matches and len(matches) == 1:
            log.debug(f"ONE MATCH: {identifier}")
            return _post_airport_selection_redirect(matches[0])

        # If multiple matches, the user will be able to select one
        # If no matches, the user can search again
        return render(
            request, "the_hangar_hub/public/airport_selection.html",
            {"identifier": identifier, "matches": matches}
        )

    except Exception as ee:
        log.error(f"Error looking up airport: {ee}")
    return HttpResponseForbidden()


@require_airport()
def select(request, airport_identifier):
    log.trace([airport_identifier])
    return _post_airport_selection_redirect(request.airport)


def router(request):
    auth = auth_service.get_auth_instance()
    after_auth = env.get_session_variable("after_auth")
    if auth.is_logged_in():
        if after_auth:
            return redirect(after_auth)
        else:
            return redirect("hub:home")
    else:
        return redirect("hub:home")


def _post_airport_selection_redirect(airport):
    airport_service.save_airport_selection(airport)
    next_url = env.get_session_variable("thh-after-ap-selection-url")
    if next_url:
        if "IDENTIFIER" in next_url:
            next_url = next_url.replace("IDENTIFIER", airport.identifier)
        log.debug(f"Sending to next URL: {next_url}")
        return redirect(next_url)
    else:
        log.debug("No next URL was found. Sending to welcome page")
        return redirect("airport:home")
        return redirect("airport:welcome", airport.identifier)