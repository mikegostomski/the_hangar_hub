from base.services import message_service, utility_service
from base.classes.util.env_helper import Log, EnvHelper
from functools import wraps
from urllib.parse import urlparse
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import resolve_url
from base.services import auth_service
from base.models.utility.error import Error

log = Log()
env = EnvHelper()


def report_errors():
    """
    Record any unhandled exceptions
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)
            except Exception as ee:
                Error.record(ee, view_func)
                raise

        return _wrapped_view
    return decorator


# ===                                ===
# === AUTHENTICATION & AUTHORIZATION ===
# ===                                ===


def require_authority(authority_code, redirect_url='/'):
    """
    Decorator for views that checks that the user has the required authority.

    authority_code: An authority_code, or a list of authority codes
    redirect_url: Where to send unauthorized user

    Example:
        from base.decorators import require_authority

        # This will redirect unauthorized users to the status test page.
        # If no redirect_url is specified, the root url will be used ("/")
        @require_authority('fake', redirect_url='base:test')
        def index(request):
            pass
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


def require_authentication(redirect_url=None):
    """
    Decorator for views that forces them to log in.

    Example:
        from base.decorators import require_authentication

        @require_authentication()
        def index(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # If not logged in, redirect
            if not request.user.is_authenticated:
                # Remember where to return after logging in
                env.set_session_variable("after_auth_url", request.path)
                # If redirecting somewhere other than default login
                if redirect_url:
                    return decorator_redirect(request, redirect_url)
                # Redirect to standard login
                else:
                    return decorator_sso_redirect(request)

            # Otherwise, render the view
            else:
                return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def require_impersonation_authority(redirect_url='/'):
    """
    Decorator for views that forces them to have access to impersonate someone else.

    Example:
        from base.decorators import require_impersonation_authority

        @require_impersonation_authority()
        def index(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):

            # If not logged in, redirect to login
            if not request.user.is_authenticated:
                return decorator_sso_redirect(request)

            # If has authority, render the view
            elif auth_service.can_impersonate():
                return view_func(request, *args, **kwargs)

            # Otherwise, send somewhere else
            else:
                message_service.post_error("You are not authorized to impersonate other users.")
                return decorator_redirect(request, redirect_url)
        return _wrapped_view
    return decorator


# ===                 ===
# === FEATURE TOGGLES ===
# ===                 ===


def require_feature(feature_code, redirect_url='/'):
    """
    Decorator for views that forces specified feature to be enabled.

    Example:
        from base.decorators import require_feature

        @require_feature('admin_script')
        def index(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # If feature is active, render the view
            if utility_service.feature_is_enabled(feature_code):
                return view_func(request, *args, **kwargs)

            # Otherwise, send somewhere else
            else:
                message_service.post_error("The requested feature is currently disabled.")
                return decorator_redirect(request, redirect_url)

        return _wrapped_view

    return decorator


def require_non_production(redirect_url='/'):
    """
    Decorator for views that limits it to non-production use only

    Example:
        from base.decorators import require_non_production

        @require_non_production()
        def test_page(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):

            # If in non-production, render the view
            if env.is_nonprod:
                return view_func(request, *args, **kwargs)

            # Otherwise, send somewhere else
            else:
                message_service.post_error("The requested page is only available in non-production environments.")
                return decorator_redirect(request, redirect_url)
        return _wrapped_view
    return decorator

#
# REMAINING GENERIC CODE IS CALLED FROM THE DECORATORS ABOVE
#


def decorator_redirect(request, redirect_url):
    resolved_login_url = resolve_url(redirect_url)
    path = request.build_absolute_uri()
    from django.contrib.auth.views import redirect_to_login
    return redirect_to_login(
        path, resolved_login_url, None
    )


def decorator_sso_redirect(request):
    resolved_login_url = resolve_url('account_login')
    path = request.build_absolute_uri()
    login_scheme, login_netloc = urlparse(resolved_login_url)[:2]
    current_scheme, current_netloc = urlparse(path)[:2]
    if ((not login_scheme or login_scheme == current_scheme) and
            (not login_netloc or login_netloc == current_netloc)):
        path = request.get_full_path()
    from django.contrib.auth.views import redirect_to_login
    return redirect_to_login(
        path, resolved_login_url, REDIRECT_FIELD_NAME
    )
