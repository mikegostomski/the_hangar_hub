from base.fixtures.timezones import timezones
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Q
from django.urls import reverse
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models.rental_models import Tenant, RentalAgreement, RentalInvoice
from base.services import message_service, date_service, utility_service
from the_hangar_hub.services import airport_service
from base.classes.breadcrumb import Breadcrumb
from datetime import datetime, timezone, timedelta
from base.models.contact.contact import Contact
from the_hangar_hub.decorators import require_airport, require_airport_manager
from base.models.utility.error import Error
from base.services import email_service
from the_hangar_hub.classes.checkout_session_helper import StripeCheckoutSessionHelper


log = Log()
env = EnvHelper()

def rental_router(request, airport_identifier=None, rental_agreement_id=None):
    """
    Return to appropriate dashboard for tenant or manager
    """
    if airport_service.manages_this_airport():
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

    co_session = StripeCheckoutSessionHelper.initiate_checkout_session(rental_agreement)
    if co_session:
        return redirect(co_session.url, code=303)
    else:
        return rental_router(request, airport_identifier, rental_agreement_id)



def rent_subscription_email(request, airport_identifier, rental_agreement_id):
    rental_agreement = RentalAgreement.get(rental_agreement_id)
    if not rental_agreement:
        message_service.post_error("Rental agreement was not found.")
        return rental_router(request)

    # # Expiration date is required
    # expiration_date = None
    # expiration_date_str = request.POST.get("expiration_date")
    # if expiration_date_str:
    #     expiration_date = date_service.string_to_date(
    #         expiration_date_str, source_timezone=rental_agreement.airport.timezone
    #     )
    #     if expiration_date:
    #         exp_local = expiration_date.astimezone(rental_agreement.airport.tz)
    #         if exp_local.hour == 0 and exp_local.minute == 0:
    #             # Expire at end-of-day
    #             expiration_date = expiration_date + timedelta(days=1)
    #         log.debug(f"EXPIRATION DATE::: {expiration_date_str}  ==> {expiration_date}")
    #     else:
    #         message_service.post_error(f"Invalid expiration date: {expiration_date_str}")
    # if not expiration_date:
    #     message_service.post_error(f"Expiration date is required")
    #     return rental_router(request)

    # Create checkout session
    co_helper = StripeCheckoutSessionHelper.initiate_checkout_session(rental_agreement)

    # Generate email to tenant
    airport = rental_agreement.airport
    hangar = rental_agreement.hangar
    tenant = rental_agreement.tenant

    airport_email = request.POST.get("airport_email") or airport.info_email


    if co_helper and co_helper.url:
        subject = f"Setup Auto-Pay for Hangar {hangar.code} at {airport.display_name}"
        email_service.send(
            subject=subject,
            content=None,
            sender=airport_email,
            to=tenant.email,
            cc=None,
            bcc=None,
            email_template="the_hangar_hub/airport/rent/management/emails/initiate_auto_pay.html",
            context={
                "url": co_helper.url,
                "airport": airport,
                "rental_agreement": rental_agreement,
                "tenant": tenant,
                "expiration_date_display": co_helper.expiration_display,
            },
            max_recipients=10,  # We rarely email more than 10 people. Exceptions should have to specify how many
            suppress_success_message=False,  # Do not notify user on successful send (but notify if send failed)
            suppress_status_messages=False,  # Do not notify user upon successful or failed send
            include_context=True,  # Include context included on all pages (current user, environment, etc)
            sender_display_name=None,  # Shortcut for: "Display Name <someone@gmail.com>",
            limit_per_second=1,
            limit_per_minute=4,
            limit_per_hour=10,
        )

    return redirect("rent:rental_invoices", airport_identifier, rental_agreement_id)





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