from django.shortcuts import redirect
from base.services import auth_service
from django.urls import reverse
from base.classes.util.app_data import Log, EnvHelper
from the_hangar_hub.services import airport_service
from the_hangar_hub.models.airport import Airport

log = Log()
env = EnvHelper()

class AirportMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Add airport to request and activate timezone if found
        get_parameter = request.GET.get("airport_identifier")
        post_parameter = request.POST.get("airport_identifier")
        airport_kwarg = view_kwargs.get("airport_identifier")
        saved_airport = airport_service.get_airport_selection()
        selected_airport = get_parameter or post_parameter or airport_kwarg or saved_airport
        log.debug(f"Middleware Airport: {selected_airport}")

        if selected_airport:
            request.airport = Airport.get(selected_airport)
            airport_service.save_airport_selection(request.airport)

            # If invalid airport identifier was included in the URL
            if selected_airport in request.path and not request.airport:
                selected_airport = None

        # If found, activate the timezone
        if hasattr(request, "airport") and request.airport:
            request.airport.activate_timezone()
            return view_func(request, *view_args, **view_kwargs)

        return None

    def __call__(self, request):
        # Render the response
        response = self.get_response(request)
        return response
