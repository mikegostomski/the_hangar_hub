from base.services import message_service, utility_service
from base.classes.util.env_helper import Log, EnvHelper
from functools import wraps
from urllib.parse import urlparse
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import resolve_url
from base.services import auth_service
from base.decorators import decorator_sso_redirect, decorator_redirect
from the_hangar_hub.services import airport_service, tenant_service
from the_hangar_hub.models.airport import Airport
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden

log = Log()
env = EnvHelper()


def require_airport(after_selection_url=None):
    """
    If an airport identifier has been saved in the session, get the Airport object and add it to the request
    If an airport has not been selected, have the user select one and save its identifier in the session
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            log.debug("Requiring AIRPORT")
            invalid_path_id = False

            # Clear any previous post-airport-selection URL
            env.set_session_variable("thh-after-ap-selection-url", None)

            # If airport already exists in the request, it was already processed in the middleware
            if hasattr(request, "airport") and type(request.airport) is Airport:
                return view_func(request, *args, **kwargs)

            get_parameter = request.GET.get("airport_identifier")
            post_parameter = request.POST.get("airport_identifier")
            airport_kwarg = kwargs.get("airport_identifier")
            saved_airport = airport_service.get_airport_selection()

            selected_airport = get_parameter or post_parameter or airport_kwarg or saved_airport
            if selected_airport:
                request.airport = Airport.get(selected_airport)

                # If invalid airport identifier was included in the URL
                if selected_airport in request.path and not request.airport:
                    invalid_path_id = selected_airport
                    selected_airport = None
                    airport_service.save_airport_selection(selected_airport)

            # If found, save it and render the view
            if hasattr(request, "airport") and request.airport:
                request.airport.activate_timezone()
                log.debug(f"Returning view func: {view_func}")
                return view_func(request, *args, **kwargs)

            # If identifier was not found or was invalid
            # Look for records of this user at an airport
            if request.user.is_authenticated:
                mgr = airport_service.managed_airport_identifiers()
                if len(mgr) == 1:
                    selected_airport = mgr[0]
                    request.airport = Airport.get(selected_airport)
                else:
                    aids = list(set(
                        [x.hangar.building.airport.identifier for x in tenant_service.get_tenant_rentals()]
                    ))
                    if len(aids) == 1:
                        selected_airport = aids[0]
                        request.airport = Airport.get(selected_airport)

                # If an airport was selected via this method, redirect to the after_selection_url
                if hasattr(request, "airport") and request.airport:
                    # The after_selection_url will default to the current url if not provided
                    log.debug(f"Saving related airport: {request.airport.identifier}")
                    airport_service.save_airport_selection(request.airport)

                    send_to = after_selection_url or request.path
                    if invalid_path_id:
                        send_to = send_to.replace(invalid_path_id, request.airport.identifier)

                    log.debug(f"Sending to {send_to}")
                    return decorator_redirect(request, send_to)

            # Identifier was still not found. Send to airport selection page
            send_to = after_selection_url or request.path
            if invalid_path_id and invalid_path_id in send_to:
                send_to = "hub:home"
            env.set_session_variable("thh-after-ap-selection-url", send_to)
            log.debug(f"Must select an airport. The redirect to {send_to}")
            return decorator_redirect(request, "hub:search")

        return _wrapped_view
    return decorator


def require_airport_manager(redirect_url='/'):
    """
    Decorator for views that require the user to be an airport manager

    redirect_url: Where to send unauthorized user
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):

            # If not logged in, redirect to login
            if not request.user.is_authenticated:
                return decorator_sso_redirect(request)

            # If user is manager for the current airport, render the view
            elif request.airport and airport_service.is_airport_manager(request.user, request.airport):
                return view_func(request, *args, **kwargs)

            # Otherwise, send somewhere else
            else:
                message_service.post_error("You are not authorized to perform the requested action")
                return decorator_redirect(request, redirect_url)
        return _wrapped_view
    return decorator


