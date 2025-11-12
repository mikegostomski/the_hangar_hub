from base.services import message_service
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from functools import wraps
from base.decorators import decorator_sso_redirect, decorator_redirect
from the_hangar_hub.services import airport_service, tenant_s
from the_hangar_hub.models.airport import Airport
from django.shortcuts import render, redirect

log = Log()
env = EnvHelper()


def require_airport():
    """
    If an airport identifier has been saved in the session, get the Airport object and add it to the request
    If an airport has not been selected, have the user select one and save its identifier in the session
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Middleware has already processed airport parameters
            if hasattr(request, "airport") and type(request.airport) is Airport:
                return view_func(request, *args, **kwargs)

            # Airport was not found. Send to airport selection page, then back to this page
            env.set_session_variable("thh-after-ap-selection-url", request.path)
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
            # Middleware has already processed airport parameters
            if hasattr(request, "airport") and type(request.airport) is Airport:
                pass
            else:
                # Airport was not found. Send to airport selection page, then back to this page
                env.set_session_variable("thh-after-ap-selection-url", request.path)
                return decorator_redirect(request, "public:search")

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

            # If airport identifier is in the path, must be a tenant at that airport
            if hasattr(request, "airport") and type(request.airport) is Airport:
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


