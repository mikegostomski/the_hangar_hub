
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
from the_hangar_hub.services import airport_service, tenant_service, application_service
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
@require_airport()
def post_comment(request, airport_identifier, request_id):
    log.trace([airport_identifier, request_id])
    this_request = MaintenanceRequest.get(request_id)
    if not this_request:
        message_service.post_error("Could not find the specified request")
        return HttpResponseForbidden()

    comment = request.POST.get("comment")
    visibility_code = request.POST.get("visibility_code") or "P"
    if not comment:
        # Assume accidental click - No message to post
        return HttpResponseForbidden()

    try:
        MaintenanceComment.objects.create(
            user=Auth.current_user(),
            mx_request=this_request,
            comment=comment,
            visibility_code=visibility_code,
        )
        return render(
            request,
            "the_hangar_hub/airport/maintenance/comments/comments.html",
            {"mx_request":MaintenanceRequest.get(request_id)}
        )
    except Exception as ee:
        Error.unexpected("Unable to post comment", ee)
        return HttpResponseForbidden()

