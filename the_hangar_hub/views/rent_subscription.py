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


log = Log()
env = EnvHelper()


@require_airport_manager()
def get_subscription_form(request, airport_identifier):
    """
    Renders the HTML form to collect subscription preferences from the airport manager
    """
    try:
        rental_id = request.GET.get("rental_id")
        rental = Rental.get(rental_id)
        if not rental:
            message_service.post_error("Rental agreement was not found.")
            return HttpResponseForbidden()

        if rental.has_subscription():
            message_service.post_error("This rental already has a Stripe subscription.")
            return HttpResponseForbidden()

        return render(
            request, "the_hangar_hub/airport/subscriptions/rent/_subscribe_form.html",
            {"rental": rental}
        )
    except Exception as ee:
        Error.record(ee)
        return HttpResponseForbidden()


@report_errors()
@require_airport_manager()
def create_subscription(request, airport_identifier):
    rental_id = request.POST.get("rental_id")
    rental = Rental.get(rental_id)
    if not rental:
        message_service.post_error("Specified rental agreement could not be found")
        return redirect("manage:buildings", airport_identifier)

    collection_start_date_str = request.POST.get("collection_start_date")
    billing_cycle_anchor = request.POST.get("billing_cycle_anchor")
    days_until_due = request.POST.get("day_until_due")


    if collection_start_date_str:
        collection_start_date = date_service.string_to_date(collection_start_date_str, request.airport.timezone)
        if not collection_start_date:
            message_service.post_error("Invalid rent collection start date")
            return redirect("manage:hangar", airport_identifier, rental.hangar.id)
        elif collection_start_date < datetime.now(timezone.utc):
            pass
            # ToDo: Prevent long-passed dates (maybe limit one month ago?)
    else:
        collection_start_date = rental.default_collection_start_date()

    if days_until_due:
        try:
            days_until_due = int(days_until_due)
        except:
            message_service.post_error("Invalid days until due. Must be a number.")
            return redirect("manage:hangar", airport_identifier, rental.hangar.id)
    else:
        days_until_due = 7

    if billing_cycle_anchor:
        try:
            billing_cycle_anchor = int(billing_cycle_anchor)
        except:
            message_service.post_error("Invalid billing period reset day. Must be 1-31")
            return redirect("manage:hangar", airport_identifier, rental.hangar.id)
    else:
        billing_cycle_anchor = None


    params = {
        "collection_start_date": collection_start_date,
        "billing_cycle_anchor": billing_cycle_anchor,
        "days_until_due": days_until_due,
    }

    subscription = stripe_service.create_rent_subscription(request.airport, rental, **params)
    if subscription:
        message_service.post_success("Rental subscription created!")
    else:
        message_service.post_error("Subscription could not be created")

    return redirect("manage:hangar", airport_identifier, rental.hangar.id)



# Invoices get created automatically when subscription is created.
#
# @report_errors()
# @require_airport_manager()
# def create_invoice(request, airport_identifier):
#     rental_id = request.POST.get("rental_id")
#     rental = Rental.get(rental_id)
#     if not rental:
#         message_service.post_error("Specified rental agreement could not be found")
#     else:
#         invoice = stripe_service.create_rent_invoice(request.airport, rental)
#         if invoice:
#             return HttpResponse("ok")
#
#     message_service.post_error("Invoice could not be created")
#     return HttpResponseForbidden()




@report_errors()
@require_airport_manager()
def delete_draft_invoice(request, airport_identifier):
    if invoice_service.delete_draft_invoice(request.POST.get("invoice_id")):
        message_service.post_success("Draft invoice deleted")
        return HttpResponse("ok")
    else:
        return HttpResponseForbidden()

