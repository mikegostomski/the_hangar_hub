from base.fixtures.timezones import timezones
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Q
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from base_stripe.models.payment_models import Customer, Subscription
from the_hangar_hub.models.rental_models import Tenant, RentalAgreement, RentalInvoice
from the_hangar_hub.models.airport_manager import AirportManager
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
    if str(hangar_id).isnumeric():
        try:
            hangar = Hangar.get(hangar_id)
            hangar_id = hangar.code
        except:
            message_service.post_error("Specified hangar ID could not be found")
            return redirect("public:home")

    # Get the rental agreement(s) for this user at this airport in this hangar
    rentals = RentalAgreement.objects.filter(
        hangar__building__airport=request.airport, tenant__user=Auth.current_user(), hangar__code=hangar_id
    ).order_by("-start_date")
    if not rentals:
        message_service.post_error("Could not find a rental agreement for you and this hangar.")
        return redirect("public:home")

    Breadcrumb.clear()
    return render(
        request, "the_hangar_hub/airport/rent/tenant/my_hangar.html",
        {
            "airport": request.airport,
            "rentals": rentals,
            "hangar": rentals[0].hangar,
        }
    )


@require_authentication()
def payment_dashboard(request):
    """
    Tenant Payment Center
    """
    current_user = Auth.current_user()
    rental_agreements = tenant_s.get_rental_agreements(current_user)
    stripe_customer = Customer.get(current_user)

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
        customer_model = Customer.get(Auth.current_user())
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
            request, "the_hangar_hub/airport/rent/tenant/payment/dashboard/_invoice_table.html",
            {
                "stripe_invoices": invoice_service.get_customer_invoices(customer_model.stripe_id, "open")
            }
        )

    except Exception as ee:
        Error.unexpected("There was an error updating your auto-pay preference", ee)
        return HttpResponseForbidden()



