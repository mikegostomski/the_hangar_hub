from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden

import the_hangar_hub.models
from base.classes.util.log import Log
from base.classes.auth.session import Auth
from base.services.message_service import post_error
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.infrastructure_models import Building, Hangar, RentalAgreement
from base.services import message_service, utility_service, email_service
from base.decorators import require_authority, require_authentication, report_errors
from the_hangar_hub.services import airport_service, tenant_service
from base.fixtures.timezones import timezones
from decimal import Decimal
from base.classes.breadcrumb import Breadcrumb
from the_hangar_hub.decorators import require_airport
import re

log = Log()


@report_errors()
@require_authentication()
@require_airport()
def my_hangar(request, airport_identifier, hangar_id):
    if str(hangar_id).isnumeric():
        try:
            hangar = Hangar.get(hangar_id)
            hangar_id = hangar.code
        except:
            message_service.post_error("Specified hangar ID could not be found")
            return redirect("hub:home")

    # Get the rental agreement(s) for this user at this airport in this hangar
    rentals = RentalAgreement.objects.filter(
        hangar__building__airport=request.airport, tenant__user=Auth.current_user(), hangar__code=hangar_id
    ).order_by("-start_date")
    if not rentals:
        message_service.post_error("Could not find a rental agreement for you and this hangar.")
        return redirect("hub:home")

    Breadcrumb.clear()
    return render(
        request, "the_hangar_hub/airport/tenant/my_hangar.html",
        {
            "airport": request.airport,
            "rentals": rentals,
            "hangar": rentals[0].hangar,
        }
    )
