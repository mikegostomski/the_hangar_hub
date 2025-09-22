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
@require_airport_manager()
def submit_review(request, application_id):
    application = _get_application_for_review(request, application_id)
    if not application:
        return redirect("application:mgmt_dashboard")

    decision = request.POST.get("decision")

    # If notes were added
    application.manager_notes_public = request.POST.get("manager_notes_public")
    application.manager_notes_private = request.POST.get("manager_notes_private")

    # If added to waitlist
    if decision == "L":
        application.wl_group_code = request.POST.get("wl_group_code")

    # If assigning a hangar, status doesn't change until a hangar has been selected
    if decision != "A":
        # Update application status
        application.change_status(decision)

    application.save()

    if decision == "A":
        return redirect("application:select", application.id)
    else:
        return redirect("application:mgmt_dashboard", application.airport.identifier)


@report_errors()
@require_airport_manager()
def select_application(request, application_id):
    application = _get_application_for_review(request, application_id)
    if not application:
        return redirect("application:mgmt_dashboard")

    application.select()
    return redirect("infrastructure:buildings", application.airport.identifier)


@report_errors()
@require_airport_manager()
def preferences(request, airport_identifier):
    airport = request.airport
    ha_preferences = airport.application_preferences()

    return render(
        request, "the_hangar_hub/airport/application/management/preferences/preference_form.html",
        {
            "airport": airport,
            "ha_preferences": ha_preferences,
        }
    )


@report_errors()
@require_airport_manager()
def save_preferences(request, airport_identifier):
    airport = request.airport
    ha_preferences = airport.application_preferences()

    required_fields = request.POST.getlist("required_fields")
    ignored_fields = request.POST.getlist("ignored_fields")

    ha_preferences.required_fields_csv = ",".join(required_fields) if required_fields else None
    ha_preferences.ignored_fields_csv = ",".join(ignored_fields) if ignored_fields else None
    ha_preferences.save()

    # Application fee is saved on the airport object
    new_fee = request.POST.get("application_fee") or 0
    old_fee = airport.application_fee_amount or 0
    if old_fee != new_fee:
        # format_decimal will clean up "$" or "," characters and make sure value is valid decimal
        decimal_string = utility_service.format_decimal(new_fee, use_commas=False, show_decimals=True)
        if not decimal_string:
            message_service.post_error("Application fee must be a valid dollar amount.")
        else:
            try:
                airport.application_fee_amount = Decimal(decimal_string)
                airport.save()
                Auth.audit(
                    "U", "AIRPORT",
                    "Updated application fee",
                    "Airport", airport.id,
                    old_fee, decimal_string
                )
            except Exception as ee:
                Error.unexpected("Unable to save application fee", ee, decimal_string)

    return redirect("application:preferences", airport.identifier)











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







@report_errors()
@require_airport_manager()
def application_dashboard(request, airport_identifier):
    log.trace([airport_identifier])
    airport = request.airport

    unreviewed = []
    incomplete = []
    for application in airport.applications.filter(status_code__in=["S", "I"]):
        if application.status_code == "S":
            unreviewed.append(application)
        elif application.status_code == "I":
            incomplete.append(application)

    Breadcrumb.add("Application Dashboard", ["application:mgmt_dashboard", airport.identifier], reset=True)
    return render(
        request, "the_hangar_hub/airport/application/management/dashboard/dashboard.html",
        {
            "unreviewed_applications": unreviewed,
            "incomplete_applications": incomplete,
        }
    )


@report_errors()
@require_airport_manager()
def change_wl_priority(request, airport_identifier):
    log.trace([airport_identifier])

    application = HangarApplication.get(request.POST.get("application_id"))
    if not application:
        message_service.post_error("Application not found. Could not update priority.")
        return HttpResponseForbidden()
    elif application.airport != request.airport:
        message_service.post_error("Application is for a different airport. If you are working in multiple tabs, try refreshing the page.")
        return HttpResponseForbidden()

    new_priority = request.POST.get("new_priority")
    if new_priority is None or new_priority not in application.wl_group_options():
        message_service.post_error("Invalid priority selection. Could not update priority.")
        return HttpResponseForbidden()

    Auth.audit(
        "U", "WAITLIST", "Updated priority", previous_value=application.wl_group_code, new_value=new_priority
    )
    application.wl_group_code = new_priority
    application.wl_index = None
    application.save()

    return render(
        request, "the_hangar_hub/airport/application/management/dashboard/_waitlist.html",
        {}
    )


@report_errors()
@require_airport_manager()
def change_wl_index(request, airport_identifier):
    application_id = request.POST.get("application_id")
    movement = request.POST.get("movement")

    # If resetting to timestamp-based order
    if movement == "reset":
        request.airport.get_waitlist().reindex_applications(group_code=None, restore_default=True)


    # Otherwise, changing one application
    else:
        application = HangarApplication.get(application_id)
        if not application:
            message_service.post_error("Application not found. Could not update waitlist position.")
            return HttpResponseForbidden()
        elif application.airport != request.airport:
            message_service.post_error("Application is for a different airport. If you are working in multiple tabs, try refreshing the page.")
            return HttpResponseForbidden()

        waitlist = request.airport.get_waitlist()
        current_position = application.wl_index
        max_position = waitlist.applications_per_group().get(application.wl_group_code)

        # Determine new position in waitlist
        if movement == "top":
            new_position = 1
        elif movement == "up":
            new_position = current_position - 1
        elif movement == "down":
            new_position = current_position + 1
        else:
            new_position = max_position
        if new_position < 1:
            new_position = 1
        if new_position > max_position:
            new_position = max_position

        log.trace([airport_identifier, application_id, movement, current_position, new_position])

        if new_position != current_position:

            for app in waitlist.applications:
                if app.wl_group_code != application.wl_group_code:
                    continue
                if app.id == application.id:
                    app.wl_index = new_position
                    app.save()
                # If moved to top, all others above it must move down one
                elif movement == "top":
                    if app.wl_index < current_position:
                        app.wl_index += 1
                        app.save()
                # If moved to bottom, all others below it must move up one
                elif movement == "bottom":
                    if app.wl_index > current_position:
                        app.wl_index -= 1
                        app.save()
                # If moved up or down one, swap with the one above/below it
                elif movement in ["up", "down"]:
                    if app.wl_index == new_position:
                        app.wl_index = current_position
                        app.save()

            Auth.audit(
                "U", "WAITLIST", "Updated index", previous_value=current_position, new_value=new_position
            )

    return render(
        request, "the_hangar_hub/airport/application/management/dashboard/_waitlist.html",
        {}
    )
