from base.fixtures.timezones import timezones
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Q
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models.tenant import Tenant, Rental
from the_hangar_hub.models.airport_manager import AirportManager
from the_hangar_hub.models.hangar import Building, Hangar
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
from base_stripe.services import customer_service, invoice_service
from django.contrib.auth.models import User
from base_stripe.models.customer import Customer


log = Log()
env = EnvHelper()


@require_authentication()
def payment_dashboard(request):
    """
    Renders the HTML form to collect subscription preferences from the airport manager
    """
    stripe_customer = customer_service.get_stripe_customer(Auth.current_user())
    stripe_invoices = invoice_service.get_customer_invoices(stripe_customer.id, "open")
    customer_model = Customer.get(stripe_customer.id)

    return render(
        request, "the_hangar_hub/airport/tenant/payment/dashboard.html",
        {
            "stripe_customer": stripe_customer,
            "stripe_invoices": stripe_invoices,
            "customer_model": customer_model,
        }
    )


@require_authentication()
def set_auto_pay(request):
    use_auto_pay = request.POST.get("use_auto_pay")
    if use_auto_pay not in ["Y", "N"]:
        return HttpResponseForbidden()
    else:
        use_auto_pay = use_auto_pay == "Y"

    # Save preference locally
    customer_model = customer_service.get_customer_model(Auth.current_user())
    customer_model.use_auto_pay = use_auto_pay
    customer_model.save()

    # ToDo: Update any open invoices to charge_automatically
    message_service.post_error("Feature not complete")
    return HttpResponseForbidden()


