from django.shortcuts import redirect
from ..services import auth_service
from django.urls import reverse
from base.classes.util.app_data import Log, EnvHelper, AppData

log = Log()
env = EnvHelper()
app = AppData()

class BaseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.
        log.debug("Using Base App")

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.user.is_authenticated:
            pass
        return None

    def __call__(self, request):
        # Is this an AWS health check or posted messages?
        posted_messages = request.path == reverse('base:messages')
        silence_logs = env.is_health_check or posted_messages

        if posted_messages:
            log.debug("Processing 'Posted Messages'...")

        # In non-prod, make the start of a new request more visible in the log (console)
        if not silence_logs:
            w = 80
            sep = '='.ljust(w, '=')
            msg = f"{request.method} {request.path} @{auth_service.get_auth_instance()}"
            log.debug(f"\n{sep}\n{msg.center(w)}\n{sep}")
            if auth_service.has_authority('~power_user'):
                env.set_session_variable('allow_limited_features', True)

        # Remove flash variables from two requests ago. Shift flash variables from last request.
        # This happens for every request EXCEPT posting messages to the screen
        if not posted_messages:
            env.cycle_flash_scope()

        # Render the response
        response = self.get_response(request)

        # After the view has completed
        env.clear_page_scope()

        if not silence_logs:
            log.end(None, request.path)

        return response
