from allauth.core.internal.ratelimit import clear

from the_hangar_hub.models.airport import Airport

from base.fixtures.timezones import timezones

from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse, FileResponse
from django.db.models import Q
import the_hangar_hub.models
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models import Tenant
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.infrastructure_models import Building, Hangar
from the_hangar_hub.models.invitation import Invitation
from base.services import message_service, utility_service, email_service, date_service
from base.decorators import require_authority, require_authentication, report_errors
from the_hangar_hub.services import airport_service, tenant_s, application_service, stripe_service
from decimal import Decimal
from base.classes.breadcrumb import Breadcrumb
from django.contrib.auth.models import User
import re
from datetime import datetime, timezone
from base.models.contact.contact import Contact
from the_hangar_hub.decorators import require_airport, require_airport_manager
import stripe
from base.models.utility.error import Error
from base_stripe.services import checkout_service
from the_hangar_hub.models.airport_manager import AirportManager
from base_upload.services import retrieval_service
from base_upload.services import upload_service
from the_hangar_hub.services.stripe import stripe_creation_svc


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from the_hangar_hub.models.airport import CustomizedContent



log = Log()
env = EnvHelper()


@report_errors()
# @require_authentication()  # ToDo: Maybe not required?
@require_airport()
def welcome(request, airport_identifier):
    """
    An individual airport's landing page
    """
    airport = request.airport

    # Airport Status
    # ==============
    if not airport.is_active():
        return render(request, "the_hangar_hub/error_pages/airport_inactive.html")
    if not airport.is_current():
        message_service.post_error("ToDo: When airport is not current???")
    has_hangars = Hangar.objects.filter(building__airport=airport).count()
    has_billing_data = airport.has_billing_data()

    # User Status
    # ===========
    is_manager = airport_service.manages_this_airport()
    rentals = tenant_s.get_rental_agreements(Auth.current_user())
    is_tenant = bool(rentals)
    on_waitlist = airport.get_waitlist().current_user_position()
    active_applications = application_service.get_active_applications(airport=airport)

    if is_manager and not has_hangars:
        return redirect("airport:manage", airport_identifier)

    return render(
        request, "the_hangar_hub/airport/welcome.html",
        {
            "is_manager": is_manager,
            "is_tenant": is_tenant,
            "on_waitlist": on_waitlist,
            "active_applications": active_applications,
        }
    )


@require_airport_manager()
def customize_content(request, airport_identifier):
    """View for airport managers to customize their airport page."""
    airport = request.airport
    customized_content = airport.customized_content
    if not customized_content:
        customized_content = CustomizedContent.objects.create(airport=airport)

    if request.method == 'POST':
        pass



    return render(request, "the_hangar_hub/airport/customized/management/index.html", {
        'customized_content': customized_content,
        'airport': airport
    })











def logo(request, airport_identifier):
    # Make sure the airport model has been queried
    airport = request.airport
    if not airport:
        airport = Airport.get(airport_identifier)
    if airport:
        logo_file = airport.get_logo()
        if logo_file:
            return retrieval_service.render_as_image(logo_file)

    # If airport was not found, or does not have a logo, display HangarHub logo
    response = FileResponse(open("the_hangar_hub/static/images/logo/hh-logo.png", "rb"))
    response["Content-Disposition"] = f'inline; filename="HangarHub-logo.png"'
    return response



@report_errors()
@require_airport_manager()
def upload_logo(request, airport_identifier):
    airport = request.airport
    uploaded_file = None
    try:
        if request.method == 'POST':
            uploaded_file = upload_service.upload_file(
                request.FILES['logo_file'],
                tag=f"logo",
                foreign_table="Airport", foreign_key=airport.id,
                # specified_filename='airport_logo',
                # parent_directory=f'airports/{airport.identifier}/logo'
            )
            log.info(f"Uploaded File: {uploaded_file}")

        if uploaded_file:
            Auth.audit(
                "C", "AIRPORT",
                f"Uploaded airport logo",
                reference_code="Airport", reference_id=airport.id
            )

            # Update tags for any previous logos for this airport
            for logo in retrieval_service.get_all_files().filter(
                tag="logo", foreign_table="Airport", foreign_key=airport.id
            ).exclude(id=uploaded_file.id):
                logo.tag = "old_logo"
                logo.save()

            return HttpResponse("ok")
    except Exception as ee:
        message_service.post_error(f"Could not update airport data: {ee}")

    return HttpResponseForbidden()

