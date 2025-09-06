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


@require_airport_manager()
def rent_collection_dashboard(request, airport_identifier):
    """
    Airport Manager view to see who is current/late on rent payments
    """
    airport = request.airport
    rentals = RentalAgreement.present_rental_agreements().filter(hangar__building__airport=airport)

    return render(
        request, "the_hangar_hub/airport/rent/management/collection/dashboard.html",
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
        return redirect("rent:rent_collection_dashboard", airport.identifier)
    if rental_agreement.airport.id != airport.id:
        message_service.post_error("Specified rental agreement is for a different airport.")
        return redirect("rent:rent_collection_dashboard", airport.identifier)

    return render(
        request, "the_hangar_hub/airport/rent/management/invoices/invoices.html",
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
        return redirect("rent:rent_collection_dashboard", airport.identifier)
    if rental_agreement.airport.id != airport.id:
        message_service.post_error("Specified rental agreement is for a different airport.")
        return redirect("rent:rent_collection_dashboard", airport.identifier)

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
        return redirect("rent:rental_invoices", airport.identifier, rental_agreement.id)

    period_start_date = date_service.string_to_date(period_start, airport.timezone)
    period_end_date = date_service.string_to_date(period_end, airport.timezone)
    if not (period_start_date and period_end_date):
        message_service.post_error("An invalid date was specified. Please check the given dates.")
        env.set_flash_scope("prefill", prefill)
        return redirect("rent:rental_invoices", airport.identifier, rental_agreement.id)

    amount_charged_decimal = utility_service.convert_to_decimal(amount_charged)
    if not amount_charged_decimal:
        log.warning(f"Invalid amount_charged: {amount_charged}")
        message_service.post_error("An invalid rent amount was specified. Please check the amount charged.")
        env.set_flash_scope("prefill", prefill)
        return redirect("rent:rental_invoices", airport.identifier, rental_agreement.id)

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

    return redirect("rent:rental_invoices", airport.identifier, rental_agreement.id)


@require_airport_manager()
def update_rental_invoice(request, airport_identifier, rental_id):
    """
    Update a rental agreement invoice
    """
    tr_html = "the_hangar_hub/airport/rent/management/invoices/_tr_invoice.html"

    airport = request.airport
    invoice = RentalInvoice.get(request.POST.get("invoice_id"))

    if not invoice:
        message_service.post_error("Could not find specified rental invoice")
        return HttpResponseForbidden()

    rental_agreement = invoice.agreement
    if rental_agreement.airport.id != airport.id:
        message_service.post_error("Specified rental invoice is for a different airport.")
        return HttpResponseForbidden()

    action = request.POST.get("action")
    if not action:
        message_service.post_warning("No action was requested. Returning to invoice list.")
        return HttpResponseForbidden()

    elif action == "cancel":
        # If not using Stripe, just mark as canceled
        if not invoice.stripe_invoice:
            invoice.status_code = "X"
            invoice.save()
            message_service.post_success("Invoice has been canceled.")
            return render(request, tr_html,{"invoice": invoice})

        else:
            # ToDo: Cancel Stripe invoice and/or subscription
            message_service.post_error("Strip cancellation not yet implemented")
            return HttpResponseForbidden()


    elif action == "waive":
        # If not using Stripe, just mark as waived
        if not invoice.stripe_invoice:
            invoice.status_code = "W"
            invoice.save()
            message_service.post_success("Invoice has been waived.")
            return render(request, tr_html,{"invoice": invoice})

        else:
            # ToDo: Waive charges for Stripe invoice and/or subscription
            message_service.post_error("Strip cancellation not yet implemented")
            return HttpResponseForbidden()


    elif action == "paid":
        # A dollar amount may be specified for partial-payment
        amount_paid = request.POST.get("amount_paid")
        if amount_paid:
            amount_paid = utility_service.convert_to_decimal(amount_paid)
            if not amount_paid:
                message_service.post_error("An invalid payment amount was specified.")
                return HttpResponseForbidden()
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
            return render(request, tr_html,{"invoice": invoice})

        else:
            # ToDo: Record payment for Stripe invoice and/or subscription
            message_service.post_error("Stripe cancellation not yet implemented")
            return HttpResponseForbidden()

    elif action == "stripe":
        # ToDo: Convert into a Stripe invoice (one-time)
        message_service.post_error("Stripe conversion not yet implemented")
        return HttpResponseForbidden()

    else:
        message_service.post_warning("Invalid action was requested. Returning to invoice list.")
        return HttpResponseForbidden()





@report_errors()
@require_airport_manager()
def add_tenant(request, airport_identifier, hangar_id):
    log.trace([airport_identifier, hangar_id])
    airport = request.airport

    hangar = airport_service.get_managed_hangar(airport, hangar_id)
    if not hangar:
        return redirect("infrastructure:buildings", airport_identifier)

    # Process Parameters
    issues = []
    email = request.POST.get("email")
    first_name = request.POST.get("first_name")
    last_name = request.POST.get("last_name")
    start_date = request.POST.get("start_date")
    end_date = request.POST.get("end_date")
    rent = request.POST.get("rent")
    deposit = request.POST.get("deposit")
    notes = request.POST.get("notes")
    log.info(f"Add Tenant: <{first_name} {last_name}> {email}")

    application_id = request.POST.get("application_id")
    application = HangarApplication.get(application_id) if application_id else None

    if not email:
        issues.append("Email address is required")

    if start_date:
        start_date = date_service.string_to_date(start_date, airport.timezone)
        if not start_date:
            issues.append("Invalid Start Date")
    else:
        start_date = datetime.now(timezone.utc)

    if end_date:
        end_date = date_service.string_to_date(end_date, airport.timezone)
    else:
        end_date = None

    if rent:
        rent = str(rent).replace('$', '').replace(',', '')
    else:
        rent = hangar.rent()
    if not rent:
        issues.append("Rent is required")

    if deposit:
        deposit = str(deposit).replace('$', '').replace(',', '')
    else:
        deposit = None


    prefill = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "start_date": start_date.strftime("%Y-%m-%d") if start_date else None,
        "end_date": end_date.strftime("%Y-%m-%d") if end_date else None,
        "rent": rent,
        "deposit": deposit,
        "notes": notes,
    }
    log.trace(prefill)

    if issues:
        env.set_flash_scope("add_tenant_issues", issues)
        env.set_flash_scope("prefill", prefill)
        return redirect("infrastructure:hangar", airport.identifier, hangar_id)


    user = contact = tenant = None

    # If application was given, get user from it
    if application:
        user = application.user
        contact = user.contact

    else:
        # Look for existing user via email
        existing_user_profile = Auth.lookup_user_profile(email)
        if existing_user_profile.id:
            user = existing_user_profile.user
            contact = existing_user_profile.contact()
            if not existing_user_profile.is_active:
                try:
                    user.is_active = True
                    user.save()
                except Exception as ee:
                    log.error(f"Unable to activate User: {user} ({ee})")

    # If not an existing user, look for existing contact record
    if not user:
        try:
            contact = Contact.objects.get(email__iexact=email)
        except Contact.DoesNotExist:
            pass

    # If user or contact exists, look for existing tenant record
    if user or contact:
        try:
            tenant = Tenant.objects.get(Q(user=user) | Q(contact=contact))
        except Tenant.DoesNotExist:
            pass

    # Contact must be created if not already found
    if not contact:
        try:
            contact = Contact()
            contact.first_name = first_name
            contact.last_name = last_name
            contact.email = email
            contact.save()
        except Exception as ee:
            log.error(f"Error creating contact: {ee}")
            issues.append("Unable to create contact record.")
    if issues:
        env.set_flash_scope("add_tenant_issues", issues)
        env.set_flash_scope("prefill", prefill)
        return redirect("infrastructure:hangar", airport_identifier, hangar_id)

    # If tenant record ws not found, create one now
    if not tenant:
        try:
            tenant = Tenant()
            tenant.contact = contact
            tenant.user = user
            tenant.save()
        except Exception as ee:
            log.error(f"Error creating tenant: {ee}")
            issues.append("Unable to create tenant record.")
    if issues:
        env.set_flash_scope("add_tenant_issues", issues)
        env.set_flash_scope("prefill", prefill)
        return redirect("infrastructure:hangar", airport.identifier, hangar_id)

    # Create the rental record
    try:
        rental = RentalAgreement()
        rental.airport = airport
        rental.tenant = tenant
        rental.hangar = hangar
        rental.start_date = start_date
        rental.end_date = end_date
        rental.rent = rent
        rental.deposit = deposit
        rental.notes = notes
        rental.save()

        message_service.post_success("New tenant has been added")
        if application:
            application.deselect()
            application.status_code = "A"
            application.save()
    except Exception as ee:
        log.error(f"Error creating rental: {ee}")
        issues.append("Unable to create rental record.")
        env.set_flash_scope("add_tenant_issues", issues)
        env.set_flash_scope("prefill", prefill)

    # If not an existing user, send an invitation
    if not user:
        Invitation.invite_tenant(airport, email, tenant=tenant, hangar=hangar)

    # Create a Stripe customer record (for sending invoices and collecting rent)
    customer_service.create_stripe_customer(full_name=f"{first_name} {last_name}", email=email, user=user)

    return redirect("infrastructure:hangar",airport_identifier, hangar.code)

