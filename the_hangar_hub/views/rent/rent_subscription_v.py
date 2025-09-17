from base.fixtures.timezones import timezones
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Q
from django.urls import reverse
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models.rental_models import Tenant, RentalAgreement, RentalInvoice
from the_hangar_hub.models.airport_manager import AirportManager
from the_hangar_hub.models.infrastructure_models import Building, Hangar
from the_hangar_hub.models.invitation import Invitation
from the_hangar_hub.models.application import HangarApplication
from base.services import message_service, date_service, utility_service
from base.decorators import require_authority, require_authentication, report_errors
from the_hangar_hub.services import airport_service
from base.classes.breadcrumb import Breadcrumb
import re
from datetime import datetime, timezone, timedelta
from base.models.contact.contact import Contact
from the_hangar_hub.decorators import require_airport, require_airport_manager
from base_upload.services import upload_service, retrieval_service
from base.models.utility.error import Error
from the_hangar_hub.services import stripe_service, stripe_s, stripe_rental_s, invoice_s
from base_stripe.models.payment_models import Customer, Subscription, Invoice
from base_stripe.services import config_service
import stripe


log = Log()
env = EnvHelper()

def rental_router(request, airport_identifier=None, rental_agreement_id=None):
    """
    Return to appropriate dashboard for tenant or manager
    """
    if airport_service.is_airport_manager(airport=request.airport):
        if rental_agreement_id:
            return redirect("rent:rental_invoices", request.airport.identifier, rental_agreement_id)
        else:
            return redirect("rent:rent_collection_dashboard", request.airport.identifier)
    else:
        if rental_agreement_id:
            return redirect("rent:tenant_dashboard")  # ToDo: Create an agreement-specific page
        else:
            return redirect("rent:tenant_dashboard")



def rent_subscription_checkout(request, airport_identifier, rental_agreement_id):
    rental_agreement = RentalAgreement.get(rental_agreement_id)
    if not rental_agreement:
        message_service.post_error("Rental agreement was not found.")
        return rental_router(request)

    # Cancel any open invoices
    invoice_s.cancel_open_invoices(rental_agreement)

    # Start subscription after any paid periods (or on agreement start date)
    collection_start_date = invoice_s.get_next_collection_start_date(rental_agreement)

    co_session = stripe_rental_s.get_subscription_checkout_session(rental_agreement, collection_start_date)
    if co_session:
        stripe_s.webhook_reaction_needed(True)
        return redirect(co_session.url, code=303)
    else:
        return rental_router(request, airport_identifier, rental_agreement_id)



def rent_subscription_create(request):
    pass












@require_airport_manager()
def get_subscription_form(request, airport_identifier):
    """
    Renders the HTML form to collect subscription preferences from the airport manager
    """
    try:
        rental_id = request.GET.get("rental_id")
        rental = RentalAgreement.get(rental_id)
        if not rental:
            message_service.post_error("Rental agreement was not found.")
            return HttpResponseForbidden()

        if rental.has_subscription():
            message_service.post_error("This rental already has a Stripe subscription.")
            return HttpResponseForbidden()

        return render(
            request, "the_hangar_hub/airport/rent/subscription_subscribe_form.html",
            {"rental": rental}
        )
    except Exception as ee:
        Error.record(ee)
        return HttpResponseForbidden()


@report_errors()
@require_airport_manager()
def create_subscription(request, airport_identifier):
    rental_id = request.POST.get("rental_id")
    rental = RentalAgreement.get(rental_id)
    if not rental:
        message_service.post_error("Specified rental agreement could not be found")
        return redirect("infrastructure:buildings", airport_identifier)

    collection_start_date_str = request.POST.get("collection_start_date")
    billing_cycle_anchor = request.POST.get("billing_cycle_anchor")
    days_until_due = request.POST.get("day_until_due")


    if collection_start_date_str:
        # This date should be in UTC, not airport's timezone  (request.airport.timezone)
        collection_start_date = date_service.string_to_date(collection_start_date_str)
        if not collection_start_date:
            message_service.post_error("Invalid rent collection start date")
            return redirect("infrastructure:hangar", airport_identifier, rental.hangar.id)
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
            return redirect("infrastructure:hangar", airport_identifier, rental.hangar.id)
    else:
        days_until_due = 7

    if billing_cycle_anchor:
        try:
            billing_cycle_anchor = int(billing_cycle_anchor)
        except:
            message_service.post_error("Invalid billing period reset day. Must be 1-31")
            return redirect("infrastructure:hangar", airport_identifier, rental.hangar.id)
    else:
        billing_cycle_anchor = None


    params = {
        "collection_start_date": collection_start_date,
        "billing_cycle_anchor": billing_cycle_anchor,
        "days_until_due": days_until_due,
    }
    log.debug(f"Subscription Params: {params}")
    subscription = stripe_service.create_rent_subscription(request.airport, rental, **params)
    if subscription:
        message_service.post_success("Rental subscription created!")
    else:
        message_service.post_error("Subscription could not be created")

    return redirect("infrastructure:hangar", airport_identifier, rental.hangar.id)



# Invoices get created automatically when subscription is created.
#
# @report_errors()
# @require_airport_manager()
# def create_invoice(request, airport_identifier):
#     rental_id = request.POST.get("rental_id")
#     rental = RentalAgreement.get(rental_id)
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
    # Subscription invoices cannot be deleted
    return HttpResponseForbidden()
    # if invoice_service.delete_draft_invoice(request.POST.get("invoice_id")):
    #     message_service.post_success("Draft invoice deleted")
    #     return HttpResponse("ok")
    # else:
    #     return HttpResponseForbidden()


@require_airport()
def refresh_rental_status(request, airport_identifier, rental_agreement_id=None):
    """
    Sync rent subscription model with Stripe data
    """
    try:
        rental = RentalAgreement.get(rental_agreement_id or request.POST.get("rental_id"))
        if rental:
            subscription = rental.get_stripe_subscription_model()
            subscription.sync()
            return HttpResponse(subscription.status)
    except Exception as ee:
        Error.record(ee)
    message_service.post_error("Unable to update rental status")
    return HttpResponseForbidden()