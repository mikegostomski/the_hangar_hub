from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden

from base.models.utility.error import EnvHelper, Log, Error
from base.classes.auth.session import Auth
from base.services.message_service import post_error
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.infrastructure_models import Building, Hangar
from base.services import message_service, utility_service, email_service, contact_service
from base.decorators import require_authority, require_authentication, report_errors
from the_hangar_hub.services import airport_service, tenant_s
from base.classes.breadcrumb import Breadcrumb
from the_hangar_hub.decorators import require_airport, require_airport_manager
from the_hangar_hub.models.application import HangarApplication
from the_hangar_hub.services import application_service
from base.models.contact.phone import Phone
from base.models.contact.address import Address
from decimal import Decimal
from the_hangar_hub.services import stripe_service
from base_stripe.services import checkout_service

log = Log()
env = EnvHelper()


@report_errors()
@require_authentication()
@require_airport()
def review_application(request, application_id):
    application = _get_application_for_review(request, application_id)
    if not application:
        return redirect("application:dashboard")

    is_manager = airport_service.is_airport_manager(airport=application.airport)
    is_applicant = application.user == Auth.current_user()

    Breadcrumb.add(f"Application Dashboard", "application:dashboard", reset=True)
    Breadcrumb.add(f"Application #{application.id}", ["application:review", application.id])
    return render(
        request, "the_hangar_hub/airport/application/shared/review/application_review.html",
        {
            "application": application,
            "is_manager": is_manager,
            "is_applicant": is_applicant,
            "airport_preferences": application.airport.application_preferences(),
        }
    )



@report_errors()
@require_authentication()
@require_airport()
def change_status(request, application_id):
    application = _get_application_for_review(request, application_id)
    if not application:
        return HttpResponseForbidden()

    new_status = request.POST.get("new_status")
    if not new_status:
        message_service.post_error("Invalid status was requested")
        return HttpResponseForbidden()
    elif new_status not in application.status_options():
        message_service.post_error("Invalid status was requested.")
        return HttpResponseForbidden()

    application.change_status(new_status)
    application.save()
    return HttpResponse(application.status)


@report_errors()
@require_authentication()
@require_airport()
def delete_application(request, application_id):
    application = _get_application_for_review(request, application_id)
    if not application:
        return redirect("application:dashboard")

    is_manager = airport_service.is_airport_manager(airport=application.airport)
    is_applicant = application.user == Auth.current_user()

    Auth.audit(
        "D", "APPLICATION",
        reference_code="HangarApplication", reference_id=application.id,
        comments=f"Deleted Application: {application.user} at {application.airport.identifier}"
    )
    application.delete()

    if is_manager:
        return redirect("application:mgmt_dashboard", request.airport.identifier)
    else:
        return redirect("application:dashboard")







def _get_application(request, application_id):
    airport = request.airport
    application = HangarApplication.get(application_id)
    if not application:
        message_service.post_error("Application could not be found.")
    elif application.airport != request.airport:
        request.airport = application.airport
        airport_service.save_airport_selection(application.airport)
        log.warning("Application airport did not match session airport")
        return application
    else:
        return application
    return None


def _get_application_for_review(request, application_id):
    user = Auth.current_user()
    application = _get_application(request, application_id)
    if application and application.user == user:
        return application
    elif application and airport_service.is_airport_manager(user, application.airport):
        return application
    message_service.post_error("Application was not found")
    return None
