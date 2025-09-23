from base.services import message_service, utility_service
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from functools import wraps
from urllib.parse import urlparse
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import resolve_url
from base.services import auth_service
from base.decorators import decorator_sso_redirect, decorator_redirect
from the_hangar_hub.services import airport_service, tenant_s
from the_hangar_hub.models.airport import Airport
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from the_hangar_hub.models.application import HangarApplication

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
            invalid_path_id = False

            # Clear any previous post-airport-selection URL
            env.set_session_variable("thh-after-ap-selection-url", None)

            # Middleware would have already processed any obvious airport
            if hasattr(request, "airport") and type(request.airport) is Airport:
                return view_func(request, *args, **kwargs)

            # Since airport was not found, check for an application (which contains an airport)
            application_kwarg = kwargs.get("application_id")
            if application_kwarg:
                ha = HangarApplication.get(application_kwarg)
                if ha:
                    request.airport = ha.airport
                    request.airport.activate_timezone()
                    airport_service.save_airport_selection(ha.airport.identifier)
                    return view_func(request, *args, **kwargs)

            # Since airport was not found, make sure there is no airport_identifier in the URL
            # If there is, it must be an invalid airport
            invalid_path_id = kwargs.get("airport_identifier")

            # If identifier was not found or was invalid
            # Look for records of this user at an airport
            if request.user.is_authenticated:
                mgr = airport_service.managed_airport_identifiers()
                if len(mgr) == 1:
                    selected_airport = mgr[0]
                    request.airport = Airport.get(selected_airport)
                else:
                    aids = list(set(
                        [x.hangar.building.airport.identifier for x in tenant_s.get_rental_agreements(Auth.current_user())]
                    ))
                    if len(aids) == 1:
                        selected_airport = aids[0]
                        request.airport = Airport.get(selected_airport)

                # If an airport was selected via this method, redirect to the after_selection_url
                if hasattr(request, "airport") and request.airport:
                    # The after_selection_url will default to the current url if not provided
                    airport_service.save_airport_selection(request.airport)

                    send_to = after_selection_url or request.path
                    if invalid_path_id:
                        send_to = send_to.replace(invalid_path_id, request.airport.identifier)

                    return decorator_redirect(request, send_to)

            # Identifier was still not found. Send to airport selection page
            send_to = after_selection_url or request.path
            if invalid_path_id and invalid_path_id in send_to:
                send_to = None
            env.set_session_variable("thh-after-ap-selection-url", send_to)
            return decorator_redirect(request, "public:search")

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
            elif airport_service.manages_this_airport():
                return view_func(request, *args, **kwargs)

            # Otherwise, send somewhere else
            else:
                message_service.post_error("You are not authorized to perform the requested action")
                return decorator_redirect(request, redirect_url)
        return _wrapped_view
    return decorator



def require_airport_tenant():
    """
    Decorator for views that require the user to be an airport tenant

    Displays a Restricted Access page if not a tenant
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):

            # If not logged in, redirect to login
            if not request.user.is_authenticated:
                return decorator_sso_redirect(request)

            # Get tenant rentals
            rentals = tenant_s.get_rental_agreements(Auth.current_user())
            if not rentals:
                return render(
                    request, "the_hangar_hub/error_pages/tenants_only.html",
                    {"rentals": rentals}
                )


            # If airport identifier is in the path, must be tenant at that airport
            if hasattr(request, "airport") and request.airport.identifier in request.path:
                this_ap_rentals = []
                for rental in rentals:
                    if rental.hangar.building.airport.identifier == request.airport.identifier:
                        this_ap_rentals.append(rental)
                if this_ap_rentals:
                    request.rentals = this_ap_rentals
                    return view_func(request, *args, **kwargs)
                else:
                    return render(
                        request, "the_hangar_hub/error_pages/tenants_only.html",
                        {"rentals": rentals}
                    )

            # If airport not in path, any rental is acceptable
            request.rentals = rentals
            return view_func(request, *args, **kwargs)

        return _wrapped_view
    return decorator


