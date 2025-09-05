from base.fixtures.timezones import timezones
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Q
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from base_stripe.models.subscription import Subscription
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
from base_stripe.services import customer_service, invoice_service
from django.contrib.auth.models import User
from base_stripe.models.customer import Customer
from base.services import utility_service

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
    rentals = RentalAgreement.present_rental_agreements().filter(hangar__building__airport=airport)

    return render(
        request, "the_hangar_hub/airport/management/rent/payments/dashboard.html",
        {
            "rentals": rentals,
        }
    )


@require_airport_manager()
def rental_invoices(request, airport_identifier, rental_id):
    """
    Manage rental agreement invoices
    """
    airport = request.airport
    rental_agreement = RentalAgreement.get(rental_id)
    if not rental_agreement:
        message_service.post_error("Could not find specified rental agreement")
        return redirect("pay:rent_collection_dashboard", airport.identifier)
    if rental_agreement.airport.id != airport.id:
        message_service.post_error("Specified rental agreement is for a different airport.")
        return redirect("pay:rent_collection_dashboard", airport.identifier)

    return render(
        request, "the_hangar_hub/airport/management/rent/payments/invoices.html",
        {
            "rental_agreement": rental_agreement,
            "blank_invoice": RentalInvoice(),
        }
    )


@require_airport_manager()
def create_rental_invoice(request, airport_identifier, rental_id):
    """
    Create a rental agreement invoice
    """
    airport = request.airport
    rental_agreement = RentalAgreement.get(rental_id)
    if not rental_agreement:
        message_service.post_error("Could not find specified rental agreement")
        return redirect("pay:rent_collection_dashboard", airport.identifier)
    if rental_agreement.airport.id != airport.id:
        message_service.post_error("Specified rental agreement is for a different airport.")
        return redirect("pay:rent_collection_dashboard", airport.identifier)

    period_start = request.POST.get("period_start")
    period_end = request.POST.get("period_end")
    amount_charged = request.POST.get("amount_charged")
    collection = request.POST.get("collection") or "airport"
    invoice_number = request.POST.get("invoice_number")

    # In case something goes wrong...
    prefill = {
        "period_start": period_start,
        "period_end": period_end,
        "amount_charged": amount_charged,
        "collection": collection,
    }

    if not (period_start and period_end and amount_charged):
        message_service.post_error("Date range and amount charged are required parameters.")
        env.set_flash_scope("prefill", prefill)
        return redirect("pay:rental_invoices", airport.identifier, rental_agreement.id)

    period_start_date = date_service.string_to_date(period_start, airport.timezone)
    period_end_date = date_service.string_to_date(period_end, airport.timezone)
    if not (period_start_date and period_end_date):
        message_service.post_error("An invalid date was specified. Please check the given dates.")
        env.set_flash_scope("prefill", prefill)
        return redirect("pay:rental_invoices", airport.identifier, rental_agreement.id)

    amount_charged_decimal = utility_service.convert_to_decimal(amount_charged)
    if not amount_charged_decimal:
        log.warning(f"Invalid amount_charged: {amount_charged}")
        message_service.post_error("An invalid rent amount was specified. Please check the amount charged.")
        env.set_flash_scope("prefill", prefill)
        return redirect("pay:rental_invoices", airport.identifier, rental_agreement.id)

    try:
        invoice = RentalInvoice.objects.create(
            agreement=rental_agreement,
            stripe_invoice=None,
            period_start_date=period_start_date,
            period_end_date=period_end_date,
            amount_charged=amount_charged_decimal,
            status_code="O",  # Open

            # If not using Stripe for invoicing
            invoice_number=invoice_number,
        )
    except Exception as ee:
        env.set_flash_scope("prefill", prefill)
        Error.unexpected("Unable to create rental invoice", ee)

    return redirect("pay:rental_invoices", airport.identifier, rental_agreement.id)


@require_airport_manager()
def update_rental_invoice(request, airport_identifier, rental_id):
    """
    Update a rental agreement invoice
    """
    airport = request.airport
    invoice = RentalInvoice.get(request.POST.get("invoice_id"))
    if not invoice:
        message_service.post_error("Could not find specified rental invoice")
        return redirect("pay:rent_collection_dashboard", airport.identifier)

    rental_agreement = invoice.agreement
    if rental_agreement.airport.id != airport.id:
        message_service.post_error("Specified rental invoice is for a different airport.")
        return redirect("pay:rent_collection_dashboard", airport.identifier)

    back_to_invoice_list = redirect("pay:rental_invoices", airport.identifier, rental_agreement.id)
    action = request.POST.get("action")
    if not action:
        message_service.post_warning("No action was requested. Returning to invoice list.")
        return back_to_invoice_list

    elif action == "cancel":
        # If not using Stripe, just mark as canceled
        if not invoice.stripe_invoice:
            invoice.status_code = "X"
            invoice.save()
            message_service.post_success("Invoice has been canceled.")
            return back_to_invoice_list

        else:
            # ToDo: Cancel Stripe invoice and/or subscription
            message_service.post_error("Strip cancellation not yet implemented")
            return back_to_invoice_list


    elif action == "waive":
        # If not using Stripe, just mark as waived
        if not invoice.stripe_invoice:
            invoice.status_code = "W"
            invoice.save()
            message_service.post_success("Invoice has been waived.")
            return back_to_invoice_list

        else:
            # ToDo: Waive charges for Stripe invoice and/or subscription
            message_service.post_error("Strip cancellation not yet implemented")
            return back_to_invoice_list


    elif action == "paid":
        # A dollar amount may be specified for partial-payment
        amount_paid = request.POST.get("amount_paid")
        if amount_paid:
            amount_paid = utility_service.convert_to_decimal(amount_paid)
            if not amount_paid:
                message_service.post_error("An invalid payment amount was specified.")
                return back_to_invoice_list
            if invoice.amount_paid and amount_paid < invoice.amount_charged:
                amount_paid = invoice.amount_paid + amount_paid
        else:
            amount_paid = invoice.amount_charged

        paid_in_full = amount_paid >= invoice.amount_charged
        payment_method_code = request.POST.get("payment_method_code")

        # If not using Stripe, just mark as paid
        if not invoice.stripe_invoice:
            invoice.amount_paid = amount_paid
            invoice.status_code = "P" if paid_in_full else "O"
            invoice.payment_method_code = payment_method_code
            if paid_in_full:
                invoice.date_paid = datetime.now(timezone.utc)
            invoice.save()
            if paid_in_full:
                message_service.post_success("Invoice has been marked as paid.")
            else:
                message_service.post_success("Partial invoice payment has been recorded.")
            return back_to_invoice_list

        else:
            # ToDo: Record payment for Stripe invoice and/or subscription
            message_service.post_error("Stripe cancellation not yet implemented")
            return back_to_invoice_list

    elif action == "stripe":
        # ToDo: Convert into a Stripe invoice (one-time)
        message_service.post_error("Stripe conversion not yet implemented")
        return back_to_invoice_list

    else:
        message_service.post_warning("Invalid action was requested. Returning to invoice list.")
        return back_to_invoice_list

    # invoice



@require_airport()
def refresh_rental_status(request, airport_identifier, rental_id=None):
    """
    Sync rent subscription model with Stripe data
    """
    try:
        rental = RentalAgreement.get(rental_id or request.POST.get("rental_id"))
        if rental:
            subscription = rental.get_stripe_subscription_model()
            subscription.sync()
            return HttpResponse(subscription.status)
    except Exception as ee:
        Error.record(ee)
    message_service.post_error("Unable to update rental status")
    return HttpResponseForbidden()