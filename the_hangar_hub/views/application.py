from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden

import the_hangar_hub.models
from base.classes.util.log import Log
from base.classes.auth.session import Auth
from base.services.message_service import post_error
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.hangar import Building, Hangar
from base.services import message_service, utility_service, email_service
from base.decorators import require_authority, require_authentication
from the_hangar_hub.services import airport_service, tenant_service
from base.fixtures.timezones import timezones
from decimal import Decimal
from base.classes.breadcrumb import Breadcrumb
import re

log = Log()

@require_authentication()
def form(request):

    return render(
        request, "the_hangar_hub/applications/form/airport_selection.html",
        {
        }
    )
