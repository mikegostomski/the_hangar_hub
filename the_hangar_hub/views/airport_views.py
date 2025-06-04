from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from base.classes.util.log import Log
from the_hangar_hub.models.airport import Airport
from base.services import message_service
log = Log()

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

def select_airport(request):
    airport_id = request.GET.get("airport_id")
    airport = Airport.get(airport_id)
    if not airport:
        message_service.post_error("Airport not found")
        return redirect("hub:welcome")

    return HttpResponse(f"You selected {airport.display_name}")


