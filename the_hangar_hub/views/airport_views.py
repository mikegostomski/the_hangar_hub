from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from base.classes.util.log import Log
from the_hangar_hub.models.airport import Airport
from base.services import message_service
from base.decorators import require_authority, require_authentication
from the_hangar_hub.services import airport_service
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
    log.debug(f"ID: {airport_id}")
    airport = Airport.get(airport_id)
    if not airport:
        message_service.post_error("Airport not found")
        return redirect("hub:welcome")

    # Get existing airport managers
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
        if is_inactive or not is_manager:
            if is_inactive:
                message_service.post_error("Your airport management status is inactive. You'll need to request access from existing management.")
            else:
                message_service.post_error("This airport already has a manager. You'll need to request access from existing management.")
            return render(
                request, "the_hangar_hub/airport/access_denied.html",
                {"airport": airport}
            )

    else:
        log.info(f"No managers exist for {airport}")
        airport_service.set_airport_manager(airport, request.user)


    return HttpResponse(f"You selected {airport.display_name}")


@require_authentication()
def manage_airport(request):
    airport_id = request.POST.get("airport_id")
    log.debug(f"ID: {airport_id}")
    airport = Airport.get(airport_id)
    if not airport:
        message_service.post_error("Airport not found")
        return redirect("hub:welcome")