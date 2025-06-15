
from the_hangar_hub.models.airport import Airport

from base.fixtures.timezones import timezones

from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Q
import the_hangar_hub.models
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models import Tenant
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.hangar import Building, Hangar
from the_hangar_hub.models.invitation import Invitation
from base.services import message_service, utility_service, email_service, date_service
from base.decorators import require_authority, require_authentication
from the_hangar_hub.services import airport_service
from decimal import Decimal
from base.classes.breadcrumb import Breadcrumb
from django.contrib.auth.models import User
import re
from datetime import datetime, timezone
from base.models.contact.contact import Contact
from the_hangar_hub.decorators import require_airport, require_airport_manager

log = Log()
env = EnvHelper()


@require_authentication()  # ToDo: Maybe not required?
@require_airport()
def welcome(request, airport_identifier):
    """
    An individual airport's landing page
    """
    airport = request.airport

    if not airport.is_active():
        return redirect("manage:claim", airport.identifier)


    return render(
        request, "the_hangar_hub/airport/welcome.html"
    )