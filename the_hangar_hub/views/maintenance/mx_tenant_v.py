
from the_hangar_hub.models.airport import Airport

from base.fixtures.timezones import timezones

from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Q
import the_hangar_hub.models
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models.maintenance import MaintenanceRequest, MaintenanceComment
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.infrastructure_models import Building, Hangar
from the_hangar_hub.models.invitation import Invitation
from base.services import message_service, utility_service, email_service, date_service
from base.decorators import require_authority, require_authentication, report_errors
from the_hangar_hub.services import airport_service, tenant_s, application_service
from decimal import Decimal
from base.classes.breadcrumb import Breadcrumb
from django.contrib.auth.models import User
import re
from datetime import datetime, timezone
from base.models.utility.error import Error
from the_hangar_hub.decorators import require_airport, require_airport_manager, require_airport_tenant

log = Log()
env = EnvHelper()


@report_errors()
@require_airport_tenant()
def tenant_dashboard(request):
    rentals = request.rentals
    requests = MaintenanceRequest.objects.filter(user=Auth.current_user())

    return render(
        request, "the_hangar_hub/airport/maintenance/tenant_dashboard/dashboard.html",
        {
            "rentals": rentals,
            "requests": requests,
        }
    )


@report_errors()
@require_airport_tenant()
def tenant_request(request, airport_identifier, hangar_id):
    rentals = request.rentals
    this_rental = None
    for rental in rentals:
        if rental.hangar.code == hangar_id:
            this_rental = rental
            break
    if not this_rental:
        message_service.post_error(f"Could not find a current rental agreement for hangar {hangar_id}")
        return redirect("mx:tenant_dashboard")

    return render(
        request, "the_hangar_hub/airport/maintenance/tenant_request/form.html",
        {
            "rental": this_rental,
        }
    )


@report_errors()
@require_airport_tenant()
def tenant_request_submit(request, airport_identifier, hangar_id):
    rentals = request.rentals
    this_rental = None
    for rental in rentals:
        if rental.hangar.code == hangar_id:
            this_rental = rental
            break
    if not this_rental:
        message_service.post_error(f"Could not find a current rental agreement for hangar {hangar_id}")
        return redirect("mx:tenant_dashboard")

    params = {
        "summary": request.POST.get("summary"),
        "notes": request.POST.get("notes"),
        "priority_code": request.POST.get("priority_code"),
    }
    has_issues = False

    if not params["summary"]:
        message_service.post_error("Summary is required.")
        has_issues = True
    if params["priority_code"] not in MaintenanceRequest.priority_options():
        message_service.post_error("Invalid priority selection.")
        has_issues = True
    if has_issues:
        env.set_flash_scope("prefill", params)
        return redirect("mx:request_form", request.airport.identifier, hangar_id)

    try:
        mx = MaintenanceRequest()
        mx.user = Auth.current_user()
        mx.tenant = this_rental.tenant
        mx.hangar = this_rental.hangar
        mx.airport = request.airport
        mx.summary = params["summary"]
        mx.notes = params["notes"]
        mx.priority_code = params["priority_code"]
        mx.status_code = "R"
        mx.save()

        message_service.post_success("Your maintenance request has been submitted")
        return redirect("mx:tenant_dashboard")

    except Exception as ee:
        Error.unexpected(
            "Unable to save your maintenance request.", ee, params
        )
        env.set_flash_scope("prefill", params)
        return redirect("mx:request_form", request.airport.identifier, hangar_id)


@report_errors()
@require_airport_tenant()
def tenant_request_view(request, airport_identifier, request_id):
    this_request = MaintenanceRequest.get(request_id)
    if not this_request:
        message_service.post_error("Could not find the specified request")
        return redirect("mx:tenant_dashboard")

    rentals = request.rentals
    this_rental = None
    for rental in rentals:
        if rental.hangar.id == this_request.hangar.id:
            this_rental = rental
            break
    if not this_rental:
        message_service.post_error(f"Could not find a current rental agreement for hangar {this_request.hangar.code}")
        return redirect("mx:tenant_dashboard")

    return render(
        request, "the_hangar_hub/airport/maintenance/tenant_request/view.html",
        {
            "mx_request": this_request,
            "rental": this_rental,
         }
    )

