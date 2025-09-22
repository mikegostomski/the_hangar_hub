
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
@require_airport_manager()
def manager_dashboard(request, airport_identifier):
    requests = MaintenanceRequest.objects.filter(hangar__building__airport__identifier=airport_identifier).exclude(
        status_code__in=["X", "C", "D"]
    )
    new_requests = [x for x in requests if x.status_code == "R"]
    requests = [x for x in requests if x.status_code != "R"]

    return render(
        request, "the_hangar_hub/airport/maintenance/manager/dashboard.html",
        {
            "new_requests": new_requests,
            "requests": requests,
        }
    )


@report_errors()
@require_airport_manager()
def manager_request_view(request, airport_identifier, request_id):
    this_request = MaintenanceRequest.get(request_id)
    if not this_request:
        message_service.post_error("Could not find the specified request")
        return redirect("mx:mx_dashboard")

    return render(
        request, "the_hangar_hub/airport/maintenance/manager/view.html",
        {
            "mx_request": this_request,
         }
    )



@report_errors()
@require_airport_manager()
def update_priority(request, airport_identifier, request_id):
    log.trace([airport_identifier, request_id])
    this_request = MaintenanceRequest.get(request_id)
    if not this_request:
        message_service.post_error("Could not find the specified request")
        return HttpResponseForbidden()

    old_priority = this_request.priority_code
    new_priority = request.POST.get("priority_code")
    if new_priority not in this_request.priority_options():
        message_service.post_error("Invalid priority selection")
        return HttpResponseForbidden()

    try:
        this_request.priority_code = new_priority
        this_request.save()
        Auth.audit(
            "U", "PRIORITY",
            "Changed request priority",
            "MaintenanceRequest", request_id,
            old_priority, new_priority
        )
        return HttpResponse("ok")
    except Exception as ee:
        Error.unexpected("Unable to save new priority", ee)
        return HttpResponseForbidden()

@report_errors()
@require_airport_manager()
def update_status(request, airport_identifier, request_id):
    log.trace([airport_identifier, request_id])
    this_request = MaintenanceRequest.get(request_id)
    if not this_request:
        message_service.post_error("Could not find the specified request")
        return HttpResponseForbidden()

    old_status = this_request.status_code
    new_status = request.POST.get("status_code")
    if new_status not in this_request.status_options():
        message_service.post_error("Invalid status selection")
        return HttpResponseForbidden()

    try:
        this_request.status_code = new_status
        this_request.save()
        Auth.audit(
            "U", "STATUS",
            "Changed request status",
            "MaintenanceRequest", request_id,
            old_status, new_status
        )
        return HttpResponse("ok")
    except Exception as ee:
        Error.unexpected("Unable to save new status", ee)
        return HttpResponseForbidden()

@report_errors()
@require_airport_manager()
def update_visibility(request, airport_identifier):
    log.trace([])
    this_comment = MaintenanceComment.get(request.POST.get("comment_id"))
    if not this_comment:
        message_service.post_error("Could not find the specified comment")
        return HttpResponseForbidden()

    old_visibility = this_comment.visibility_code
    new_visibility = request.POST.get("visibility_code")
    if new_visibility not in this_comment.visibility_options():
        message_service.post_error("Invalid visibility selection")
        return HttpResponseForbidden()

    try:
        this_comment.visibility_code = new_visibility
        this_comment.save()
        Auth.audit(
            "U", "COMMENT",
            f"Changed visibility on comment #{this_comment.id}",
            "MaintenanceRequest", this_comment.mx_request.id,
            old_visibility, new_visibility
        )
        return render(
            request,
            "the_hangar_hub/airport/maintenance/comments/comments.html",
            {"mx_request": MaintenanceRequest.get(this_comment.mx_request.id)}
        )
    except Exception as ee:
        Error.unexpected("Unable to save new visibility", ee)
        return HttpResponseForbidden()
