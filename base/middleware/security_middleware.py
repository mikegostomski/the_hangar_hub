from django.shortcuts import redirect
from ..services import message_service, validation_service, auth_service
from ..models.utility.xss_attempt import XssAttempt
from django.urls import reverse
from django.http import HttpResponseForbidden, HttpResponse

from base.classes.util.app_data import Log, EnvHelper, AppData

log = Log()
env = EnvHelper()
app = AppData()


def xss_prevention(get_response):
    def script_response(param, value, is_ajax, path, session_key=None):

        # Log the suspicious parameter
        log.error(f"Potential XSS attempt in '{param}' parameter")
        log.info(f"\n{value}\n")

        # Store attempt in database.
        auth = auth_service.get_auth_instance()
        xss_instance = XssAttempt(
            path=path,
            user_username=auth.authenticated_user.username if auth.authenticated_user else None,
            parameter_name=param,
            parameter_value=value,
            session_key=session_key,
        )
        xss_instance.save()

        # Also log it in the audit table.
        auth.audit("C", "XSS", comments=f"Created XSS attempt record #{xss_instance.id}")

        if is_ajax:
            # Generate a "posted message" to display on the view
            message_service.post_error("Suspicious input detected. Unable to process request.")

            # Return as failure for AJAX calls
            return HttpResponseForbidden()
        else:
            return redirect('base:xss_block')

    def xss_middleware(request):

        # Gather conditions and values used later
        is_ajax = env.is_ajax
        is_terminating_impersonation = request.path == reverse('base:stop_impersonating')
        is_logging_out = request.path == reverse('account_logout')
        is_health_check = env.is_health_check
        is_posted_messages = request.path == reverse('base:messages')
        is_xss_lock = request.path == reverse('base:xss_lock')

        # Script_response will return a redirect.  If there are multiple XSS attempts, all attempts
        # should be logged, but only one return is needed. Store it in a variable while iterating.
        script_response_value = None

        # Iterate through GET parameters
        for param, value in request.GET.items():
            if validation_service.contains_script(value):
                # If XSS attempt was found, log it and get a Redirect
                script_response_value = script_response(param, value, is_ajax, request.path, request.session.session_key)

        # Iterate through POST parameters
        for param, value in request.POST.items():
            if validation_service.contains_script(value):
                # If XSS attempt was found, log it and get a Redirect
                script_response_value = script_response(param, value, is_ajax, request.path, request.session.session_key)

        # If xss was found, return the Redirect to the blocking page
        if script_response_value is not None:
            return script_response_value

        # If not already loading the lock page (and not an AWS health check)
        if not (is_xss_lock or is_health_check or is_posted_messages):
            auth = auth_service.get_auth_instance()
            user_id = auth.authenticated_user.id

            # Locked out users may log out or stop impersonating
            if user_id and not(is_terminating_impersonation or is_logging_out):
                # Count the number of un-reviewed XSS attempts for this user
                attempts = len(XssAttempt.objects.filter(user_username=auth.authenticated_user.username, reviewer_username__isnull=True))
                # After 3 attempts, user is locked out of site
                if attempts >= 3:
                    return redirect('base:xss_lock')

            # Unauthenticated users will just have a counter in their session
            elif not user_id:
                xss_attempts = env.get_session_variable("xss_attempt_counter", 0)
                if xss_attempts >= 3:
                    return redirect("base:xss_lock")

        # Otherwise, continue normally (and add XSS-Protection header)
        response = get_response(request)
        if type(response) is HttpResponse:
            response["X-XSS-Protection"] = "1"

            # Also add Cache-control: no-store and Pragma: no-cache headers (recommended by security team)
            response["Cache-Control"] = "no-store"
            response["Pragma"] = "no-cache"
        # else:
        #     log.info(f"Security headers not added to {type(response)}")

        return response

    return xss_middleware
