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
from the_hangar_hub.decorators import require_airport, require_airport_manager
from the_hangar_hub.models.application import HangarApplication
import re

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

    airport_preferences = application.airport.application_preferences()

    Breadcrumb.add("Hangar Application", ["apply:resume", application.id], reset=True)
    return render(
        request, "the_hangar_hub/airport/application/form/application_form.html",
        {
            "airport": airport,
            "application": application,
            "applicant": applicant,
            "airport_preferences": airport_preferences,
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
        return HttpResponse("Go to application review page")


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











def _get_user_application(request, application_id):
    airport = request.airport
    applicant = Auth.current_user_profile()
    application = HangarApplication.get(application_id)
    if not application:
        message_service.post_error("Application could not be found.")
    elif application.airport != airport:
        message_service.post_error("Application was not found.")
    elif application.user != applicant.user:
        message_service.post_error("Application was not found")
    else:
        return application
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
        application.save()
        return True
    except Exception as ee:
        log.error(f"Error saving application: {ee}")
        message_service,post_error("There was an issue saving the form.")
        return False
