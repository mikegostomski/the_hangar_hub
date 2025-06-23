from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden

import the_hangar_hub.models
from base.classes.util.log import Log
from base.classes.auth.session import Auth
from base.services.message_service import post_error
from the_hangar_hub.asgi import application
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.hangar import Building, Hangar
from base.services import message_service, utility_service, email_service, contact_service
from base.decorators import require_authority, require_authentication
from the_hangar_hub.services import airport_service, tenant_service
from base.fixtures.timezones import timezones
from decimal import Decimal
from base.classes.breadcrumb import Breadcrumb
from the_hangar_hub.decorators import require_airport, require_airport_manager
from the_hangar_hub.models.application import HangarApplication
import re
from base.models.contact.phone import Phone
from base.models.contact.address import Address

log = Log()

@require_authentication()
@require_airport()
def form(request, airport_identifier=None, application_id=None):
    airport = request.airport
    applicant = Auth.current_user_profile()
    application = None

    if application_id:
        application = _get_user_application(request, application_id)
        if not application:
            message_service.post_error("The specified application could not be found.")
        else:
            airport = application.airport
            airport_service.save_airport_selection(airport)

    if not application:
        # Look for existing Incomplete application for this user/airport
        application = HangarApplication.start(airport, applicant.user)

    elif application.status_code in ["S", "R", "A", "D"]:
        return redirect("apply:review", application.id)

    airport_preferences = application.airport.application_preferences()

    Breadcrumb.add("Hangar Application", ["apply:resume", application.id], reset=True)
    return render(
        request, "the_hangar_hub/airport/application/form/application_form.html",
        {
            "airport": airport,
            "application": application,
            "applicant": applicant,
            "airport_preferences": airport_preferences,
            'phone_options': Phone.phone_types(),
            'address_options': Address.address_types(),
        }
    )


@require_authentication()
@require_airport()
def save(request, application_id):
    application = _get_user_application(request, application_id)
    if not application:
        return HttpResponseForbidden()
    elif _save_application_fields(request, application):
        return HttpResponse("ok")
    else:
        return HttpResponseForbidden()


@require_authentication()
@require_airport()
def submit(request, application_id):
    application = _get_user_application(request, application_id)
    if not application:
        return HttpResponseForbidden()

    if not _save_application_fields(request, application):
        return HttpResponseForbidden()

    # Validate fields...
    issues = []
    try:
        airport_preferences = application.airport.application_preferences()
        for ff in airport_preferences.fields():
            attr = ff.name
            val = getattr(application, attr)
            if attr in airport_preferences.required_fields and not val:
                issues.append(f"{ff.verbose_name} is a required field.")

        if not issues:
            application.change_status("S")
            application.save()
    except Exception as ee:
        issues.append("There was an error submitting your application.")

    if issues:
        msg = ["There were issues submitting your application:<ul>"]
        for ii in issues:
            msg.append(f"<li>{ii}</li>")
        msg.append("</ul>")
        message_service.post_error("".join(msg))

        return redirect("apply:resume", application.id)
    else:
        return redirect("apply:review", application.id)


@require_authentication()
@require_airport()
def review_application(request, application_id):
    application = _get_application_for_review(request, application_id)
    if not application:
        return redirect("hub:home")

    is_manager = airport_service.is_airport_manager(airport=application.airport)
    is_applicant = application.user == Auth.current_user()

    Breadcrumb.add(f"Application #{application.id}", ["apply:review", application.id], reset=True)
    return render(
        request, "the_hangar_hub/airport/application/review/application_review.html",
        {
            "application": application,
            "is_manager": is_manager,
            "is_applicant": is_applicant,
            "airport_preferences": application.airport.application_preferences(),
        }
    )



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


@require_authentication()
@require_airport()
def delete_application(request, application_id):
    application = _get_application_for_review(request, application_id)
    if not application:
        return redirect("hub:home")

    is_manager = airport_service.is_airport_manager(airport=application.airport)
    is_applicant = application.user == Auth.current_user()

    Auth.audit(
        "D", "APPLICATION",
        reference_code="HangerApplication", reference_id=application.id,
        comments=f"Deleted Application: {application.user} at {application.airport.identifier}"
    )
    application.delete()

    if is_manager:
        return redirect("manage:application_dashboard", request.airport.identifier)
    else:
        return redirect("hub:home")


@require_authentication()
@require_airport()
@require_airport_manager()
def preferences(request, airport_identifier):
    airport = request.airport
    ha_preferences = airport.application_preferences()

    return render(
        request, "the_hangar_hub/airport/application/preferences/preference_form.html",
        {
            "airport": airport,
            "ha_preferences": ha_preferences,
        }
    )


@require_authentication()
@require_airport()
@require_airport_manager()
def save_preferences(request, airport_identifier):
    airport = request.airport
    ha_preferences = airport.application_preferences()

    required_fields = request.POST.getlist("required_fields")
    ignored_fields = request.POST.getlist("ignored_fields")

    ha_preferences.required_fields_csv = ",".join(required_fields) if required_fields else None
    ha_preferences.ignored_fields_csv = ",".join(ignored_fields) if ignored_fields else None
    ha_preferences.save()

    return redirect("apply:preferences", airport.identifier)











def _get_application(request, application_id):
    airport = request.airport
    application = HangarApplication.get(application_id)
    if not application:
        message_service.post_error("Application could not be found.")
    elif application.airport != airport:
        message_service.post_error("Application was not found.")
    else:
        return application
    return None

def _get_user_application(request, application_id):
    applicant = Auth.current_user_profile()
    application = _get_application(request, application_id)
    if application and application.user == applicant.user:
        return application
    message_service.post_error("The specified application does not belong to you.")
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

def _save_application_fields(request, application):
    try:
        application.preferred_phone = application.user.contact.phone_number_options().get(request.POST.get("preferred_phone"))
        application.mailing_address = application.user.contact.address_options().get(request.POST.get("mailing_address"))

        for attr in [
            "preferred_email",
            "hangar_type_code", "aircraft_type_code",
            "aircraft_make", "aircraft_model",
            "aircraft_wingspan", "aircraft_height",
            "registration_number", "plane_notes"
        ]:
            setattr(application, attr, request.POST.get(attr) or None)

        # If no phones in profile, user had a set of phone inputs instead of a select menu
        if request.POST.get("phone_number"):
            preferred_phone = contact_service.add_phone_from_request(request, application.user.contact)
            if preferred_phone:
                application.preferred_phone = preferred_phone
        # If no address in profile, user had a set of address inputs instead of a select menu
        if request.POST.get("address_type"):
            mailing_address = contact_service.add_address_from_request(request, application.user.contact)
            if mailing_address:
                application.mailing_address = mailing_address

        application.save()
        return True
    except Exception as ee:
        log.error(f"Error saving application: {ee}")
        message_service,post_error("There was an issue saving the form.")
        return False
