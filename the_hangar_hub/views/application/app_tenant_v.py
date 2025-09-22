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
def dashboard(request):
    applications = HangarApplication.objects.filter(user=Auth.current_user())

    Breadcrumb.add(f"Application Dashboard", "application:dashboard", reset=True)
    return render(
        request, "the_hangar_hub/airport/application/tenant/dashboard/application_dashboard.html",
        {
            "applications": applications,
        }
    )




@report_errors()
@require_authentication()
@require_airport()
def form(request, airport_identifier=None, application_id=None):
    airport = request.airport
    applicant = Auth.current_user_profile()
    application = None

    if application_id:
        log.debug(f"Retrieve application #{application_id}")
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
        return redirect("application:review", application.id)

    airport_preferences = application.airport.application_preferences()

    Breadcrumb.add(f"Application Dashboard", "application:dashboard", reset=True)
    Breadcrumb.add("Hangar Application", ["application:resume", application.id])
    return render(
        request, "the_hangar_hub/airport/application/tenant/form/application_form.html",
        {
            "airport": airport,
            "application": application,
            "applicant": applicant,
            "airport_preferences": airport_preferences,
            'phone_options': Phone.phone_types(),
            'address_options': Address.address_types(),
        }
    )


@report_errors()
@require_authentication()
@require_airport()
def save(request, application_id):
    application = _get_user_application(request, application_id)
    if not application:
        return HttpResponseForbidden()
    elif _save_application_fields(request, application):
        message_service.post_success("Application data has been saved")
        return HttpResponse("ok")
    else:
        return HttpResponseForbidden()


@report_errors()
@require_authentication()
@require_airport()
def submit(request, application_id):
    airport = request.airport
    application = _get_user_application(request, application_id)
    if not application:
        return redirect("application:resume", application.id)

    if not _save_application_fields(request, application):
        return redirect("application:resume", application.id)

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
            if airport.application_fee_amount:
                application.change_status("P")
            else:
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

        return redirect("application:resume", application.id)

    else:
        if application.status_code == "P":
            co = stripe_service.get_checkout_session_application_fee(application)
            session_id = co.id
            env.set_session_variable(f"cs_applicationFee_{application_id}", session_id)
            log.info(f"Checkout Session ID: {session_id}")

            # Must pay application fee
            return redirect(co.url, code=303)

        else:
            return redirect("application:dashboard")


@report_errors()
@require_authentication()
@require_airport()
def record_payment(request, application_id):
    airport = request.airport
    application = _get_user_application(request, application_id)

    if checkout_service.verify_checkout(
            session_var=f"cs_applicationFee_{application_id}", account_id=airport.stripe_account_id
    ):
        message_service.post_success("Application fee has been paid")
        if not application:
            Error.unexpected(
                "Unable to mark application as submitted.",
                "Payment succeeded, but application not found.",
                application_id
            )
        else:
            try:
                application.change_status("S")  # Submitted
                application.fee_payment_method = "STRIPE"
                application.fee_amount = airport.application_fee_amount
                application.fee_status = "P"  # Paid
                application.save()
            except Exception as ee:
                Error.unexpected(
                    "Unable to mark application as submitted",
                    ee,
                    application_id
                )
        return redirect("application:review", application_id)
    else:
        message_service.post_error("Application fee has not been paid")

    return redirect("application:resume", application_id)










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

def _get_user_application(request, application_id):
    applicant = Auth.current_user_profile()
    application = _get_application(request, application_id)
    if application and application.user == applicant.user:
        return application
    elif application:
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
            "registration_number", "applicant_notes"
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
