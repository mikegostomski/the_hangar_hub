from base.fixtures.timezones import timezones
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Q
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from base_stripe.models.subscription import Subscription
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
    Tenant Payment Center
    """
    stripe_customer = customer_service.get_stripe_customer(Auth.current_user())
    open_invoices = invoice_service.get_customer_invoices(stripe_customer.id, "open")
    recent_invoices = invoice_service.get_customer_invoices(stripe_customer.id, "paid", since_days=180)
    customer_model = Customer.get(stripe_customer.id)

    return render(
        request, "the_hangar_hub/airport/tenant/payment/dashboard/dashboard.html",
        {
            "stripe_customer": stripe_customer,
            "open_invoices": open_invoices,
            "recent_invoices": recent_invoices,
            "customer_model": customer_model,
        }
    )


@require_authentication()
def set_auto_pay(request):
    """
    Allow tenants to enable/disable auto-pay
    """
    try:
        use_auto_pay = request.POST.get("use_auto_pay")
        if use_auto_pay not in ["Y", "N"]:
            return HttpResponseForbidden()
        else:
            use_auto_pay = use_auto_pay == "Y"

        # Save preference locally
        customer_model = customer_service.get_customer_model(Auth.current_user())
        customer_model.use_auto_pay = use_auto_pay
        customer_model.save()
        message_service.post_success(f"Updated auto-pay preference.")

        # Invoices associated with subscriptions may not be modified
        # If there are open invoices, alert the tenant that their invoice was not updated
        open_invoices = invoice_service.get_customer_invoices(customer_model.stripe_id, "open")
        if open_invoices:
            sample = open_invoices[0]
            if sample.auto_pay != use_auto_pay:
                if sample.auto_pay:
                    message_service.post_info(f"""
                        bi-bell Your existing invoice will still be auto-paid. 
                        You may be able to change this in the 
                        <a href="{env.get_setting('STRIPE_PORTAL_LINK')}" target="_blank">Stripe Customer Portal</a>.
                    """)
                else:
                    message_service.post_info(f"""
                        bi-bell Your existing invoice must still be paid manually. 
                        Use the "Pay Now" link to pay your invoice.
                    """)


        #
        # # Update any open invoices to charge_automatically
        # try:
        #     open_invoices = invoice_service.get_customer_invoices(customer_model.stripe_id, "open")
        #     if open_invoices:
        #         update_count = fail_count = 0
        #         for inv in open_invoices:
        #             inv.collection_method = "charge_automatically" if use_auto_pay else "send_invoice"
        #             if inv.update_stripe():
        #                 update_count += 1
        #             else:
        #                 fail_count += 1
        #         if update_count:
        #             s = "" if update_count == 1 else "s"
        #             message_service.post_success(f"Updated auto-pay preference for {update_count} open invoice{s}")
        #         if fail_count:
        #             s = "" if fail_count == 1 else "s"
        #             message_service.post_error(f"Unable to update auto-pay preference for {fail_count} open invoice{s}")
        # except Exception as ee:
        #     Error.unexpected("There was an error updating your open invoices", ee)

        return render(
            request, "the_hangar_hub/airport/tenant/payment/dashboard/_invoice_table.html",
            {
                "stripe_invoices": invoice_service.get_customer_invoices(customer_model.stripe_id, "open")
            }
        )

    except Exception as ee:
        Error.unexpected("There was an error updating your auto-pay preference", ee)
        return HttpResponseForbidden()


@require_airport_manager()
def rent_collection_dashboard(request, airport_identifier):
    """
    Airport Manager view to see who is current/late on rent payments
    """
    airport = request.airport
    rentals = Rental.current_rentals().filter(hangar__building__airport=airport)

    return render(
        request, "the_hangar_hub/airport/management/rent/payments/dashboard.html",
        {
            "rentals": rentals,
        }
    )


@require_airport()
def refresh_rental_status(request, airport_identifier, rental_id=None):
    """
    Sync rent subscription model with Stripe data
    """
    try:
        rental = Rental.get(rental_id or request.POST.get("rental_id"))
        if rental:
            subscription = rental.get_stripe_subscription_model()
            subscription.sync()
            return HttpResponse(subscription.status)
    except Exception as ee:
        Error.record(ee)
    message_service.post_error("Unable to update rental status")
    return HttpResponseForbidden()