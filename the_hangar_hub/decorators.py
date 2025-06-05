from base.services import message_service, utility_service
from base.classes.util.env_helper import Log, EnvHelper
from functools import wraps
from urllib.parse import urlparse
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import resolve_url
from base.services import auth_service
from base.decorators import decorator_sso_redirect, decorator_redirect

log = Log()
env = EnvHelper()


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

            # If has authority, render the view
            elif auth_service.has_authority(authority_code):
                return view_func(request, *args, **kwargs)

            # Otherwise, send somewhere else
            else:
                message_service.post_error("You are not authorized to perform the requested action")
                return decorator_redirect(request, redirect_url)
        return _wrapped_view
    return decorator


