from django.shortcuts import redirect
from base.services import auth_service
from django.urls import reverse
from base.classes.util.app_data import Log, EnvHelper

log = Log()
env = EnvHelper()

class AirportMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        log.debug("Airport Middleware")

    def process_view(self, request, view_func, view_args, view_kwargs):
        # ToDo: Add airport to request and activate timezone?
        return None

    def __call__(self, request):
        # ToDo: Add airport to request and activate timezone?

        # Render the response
        response = self.get_response(request)
        return response
