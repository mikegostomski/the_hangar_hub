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


log = Log()
env = EnvHelper()


@require_authentication()
def payment_dashboard(request):
    """
    Renders the HTML form to collect subscription preferences from the airport manager
    """
    customer_service.get_stripe_customer()
    customer_rec = User.objects.get(stripe_customer__user=Auth.current_user())
    return HttpResponse(customer_rec)
