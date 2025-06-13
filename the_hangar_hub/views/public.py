from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from base.classes.util.env_helper import Log, EnvHelper
from base.services import auth_service
from the_hangar_hub.decorators import require_airport
from the_hangar_hub.models.airport import Airport
log = Log()
env = EnvHelper()

def home(request):
    return render(request, "the_hangar_hub/public/about.html")


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
            return redirect("hub:select", identifier)

        # If multiple matches, the user will be able to select one
        # If no matches, the user can search again
        return render(
            request, "the_hangar_hub/airport_selection.html",
            {"identifier": identifier, "matches": matches}
        )

    except Exception as ee:
        log.error(f"Error looking up airport: {ee}")
    return HttpResponseForbidden()


@require_airport()
def select(request, airport_identifier):
    next_url = env.get_session_variable("thh-after-ap-selection-url")
    if next_url:
        return redirect(next_url)
    else:
        return redirect("airport:welcome", airport_identifier)


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

