from base.fixtures.timezones import timezones
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Q
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from base_stripe.models.payment_models import StripeCustomer, StripeSubscription
from the_hangar_hub.models.rental_models import Tenant, RentalAgreement, RentalInvoice
from the_hangar_hub.models.maintenance import MaintenanceRequest, ScheduledMaintenance
from the_hangar_hub.models.infrastructure_models import Building, Hangar
from the_hangar_hub.models.invitation import Invitation
from the_hangar_hub.models.application import HangarApplication
from base.services import message_service, date_service
from base.decorators import require_authority, require_authentication, report_errors
from the_hangar_hub.services import airport_service
from base.classes.breadcrumb import Breadcrumb
import re
from datetime import datetime, timezone
from base.models.contact.contact import Contact
from the_hangar_hub.decorators import require_airport, require_airport_manager
from base_upload.services import upload_service, retrieval_service
from base.models.utility.error import Error
from the_hangar_hub.services import stripe_service
from base_stripe.services import invoice_service
from django.contrib.auth.models import User
from base.services import utility_service
from the_hangar_hub.services import tenant_s


log = Log()
env = EnvHelper()


@report_errors()
@require_authentication()
@require_airport()
def my_hangar(request, airport_identifier, hangar_id):
    hangar = Hangar.get(hangar_id)
    if not hangar:
        message_service.post_error("Specified hangar ID could not be found")
        return redirect("public:home")

    # Get the rental agreement(s) for this user at this airport in this hangar
    rentals = RentalAgreement.objects.filter(
        airport=request.airport, tenant__user=Auth.current_user(), hangar=hangar
    ).order_by("-start_date")
    if not rentals:
        message_service.post_error("Could not find a rental agreement for you and this hangar.")
        return redirect("public:home")

    # Look for maintenance requests
    mx_requests = MaintenanceRequest.objects.filter(airport=request.airport, hangar=hangar)


    Breadcrumb.clear()
    return render(
        request, "the_hangar_hub/airport/rent/tenant/my_hangar.html",
        {
            "airport": request.airport,
            "rentals": rentals,
            "hangar": hangar,
            "mx_requests": mx_requests
        }
    )


@require_authentication()
def payment_dashboard(request):
    """
    Tenant Payment Center
    """
    current_user = Auth.current_user()
    rental_agreements = tenant_s.get_rental_agreements(current_user)
    stripe_customer = StripeCustomer.get(current_user)

    stripe_customer.sync()

    # open_invoices = invoice_service.get_customer_invoices(stripe_customer.id, "open")
    # recent_invoices = invoice_service.get_customer_invoices(stripe_customer.id, "paid", since_days=180)
    # customer_model = Customer.get(stripe_customer.id)

    return render(
        request, "the_hangar_hub/airport/rent/tenant/payment/dashboard/dashboard.html",
        {
            "rental_agreements": rental_agreements,
            "stripe_customer": stripe_customer,
        }
    )

