from django.shortcuts import redirect
from base.services import auth_service
from django.urls import reverse
from base.classes.util.app_data import Log, EnvHelper
from the_hangar_hub.services import airport_service, tenant_s
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.application import HangarApplication

log = Log()
env = EnvHelper()

class AirportMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.path == "/stripe/webhook":
            return None

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
                log.warning(f"Airport included in URL was not found ({selected_airport})")

                # Look for records of this user at an airport
                if request.user.is_authenticated:
                    # Is user an airport manager?
                    mgr = airport_service.managed_airport_identifiers()
                    if len(mgr) == 1:
                        request.airport = Airport.get(mgr[0])
                    else:
                        # Is user an airport tenant?
                        rental_agreements = tenant_s.get_rental_agreements(request.user)
                        aids = list(set(
                            [x.airport.identifier for x in rental_agreements or []]
                        ))
                        if len(aids) == 1:
                            request.airport = Airport.get(aids[0])

                    # If airport was found, redirect to URL with appropriate airport identifier
                    if request.airport:
                        old_path = request.path
                        new_path = request.path.replace(selected_airport, request.airport.identifier)
                        if old_path != new_path:
                            return redirect(new_path)

        # If no airport found, look for an application
        get_parameter = request.GET.get("application_id")
        post_parameter = request.POST.get("application_id")
        kwarg = view_kwargs.get("application_id")
        application_id = get_parameter or post_parameter or kwarg
        if application_id:
            ha = HangarApplication.get(application_id)
            if ha:
                request.airport = ha.airport
                airport_service.save_airport_selection(request.airport)

        # If an airport was found...
        if hasattr(request, "airport") and request.airport:
            # Activate the airport's timezone
            request.airport.activate_timezone()

            return view_func(request, *view_args, **view_kwargs)

        return None

    def __call__(self, request):
        # Render the response
        response = self.get_response(request)
        return response
