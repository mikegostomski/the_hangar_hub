from base.fixtures.timezones import timezones
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.db.models import Q
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from base_stripe.models.payment_models import StripeSubscription
from the_hangar_hub.models.rental_models import Tenant, RentalAgreement, RentalInvoice
from the_hangar_hub.models.airport_customer import AirportCustomer
from the_hangar_hub.models.airport_manager import AirportManager
from the_hangar_hub.models.infrastructure_models import Building, Hangar
from the_hangar_hub.models.invitation import Invitation
from the_hangar_hub.models.application import HangarApplication
from base.services import message_service, date_service
from base.decorators import require_authority, require_authentication, report_errors
from the_hangar_hub.services import airport_service
from the_hangar_hub.services.rental import invoice_svc
from base.classes.breadcrumb import Breadcrumb
import re
from datetime import datetime, timezone
from base.models.contact.contact import Contact
from the_hangar_hub.decorators import require_airport, require_airport_manager
from base_upload.services import upload_service, retrieval_service
from base.models.utility.error import Error
from the_hangar_hub.services import stripe_service
from django.contrib.auth.models import User
from base_stripe.models.payment_models import StripeCustomer
from base.services import utility_service
from base_stripe.services import invoice_service as stripe_invoice_service
from the_hangar_hub.services import stripe_rental_s
from the_hangar_hub.services.rental import agreement_svc

log = Log()
env = EnvHelper()


@require_airport_manager()
def rent_collection_dashboard(request, airport_identifier):
    """
    Airport Manager view to see who is current/late on rent payments
    """
    airport = request.airport
    rentals = RentalAgreement.relevant_rental_agreements().filter(airport=airport)

    return render(
        request, "the_hangar_hub/airport/rent/management/collection/dashboard.html",
        {
            "rentals": rentals,
        }
    )


@require_airport_manager()
def rental_invoices(request, airport_identifier, rental_agreement_id):
    """
    Manage rental agreement invoices
    """
    airport = request.airport
    rental_agreement = RentalAgreement.get(rental_agreement_id)
    stripe_rental_s.sync_rental_agreement_subscriptions(rental_agreement)
    stripe_rental_s.sync_rental_agreement_invoices(rental_agreement)

    if not rental_agreement:
        message_service.post_error("Could not find specified rental agreement")
        return redirect("rent:rent_collection_dashboard", airport.identifier)
    if rental_agreement.airport.id != airport.id:
        message_service.post_error("Specified rental agreement is for a different airport.")
        return redirect("rent:rent_collection_dashboard", airport.identifier)

    if rental_agreement.customer:
        rental_agreement.customer.sync()

    return render(
        request, "the_hangar_hub/airport/rent/management/invoices/invoices.html",
        {
            "rental_agreement": rental_agreement,
            "blank_invoice": RentalInvoice(),
        }
    )


@require_airport_manager()
def create_rental_invoice(request, airport_identifier, rental_agreement_id):
    """
    Create a rental agreement invoice
    """
    airport = request.airport
    rental_agreement = RentalAgreement.get(rental_agreement_id)
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

    invoice = invoice_svc.create_rental_invoice(
        rental_agreement, period_start, period_end, amount_charged, collection, invoice_number
    )

    if not invoice:
        prefill = {
            "period_start": period_start,
            "period_end": period_end,
            "amount_charged": amount_charged,
            "collection": collection,
        }
        env.set_flash_scope("prefill", prefill)
        return redirect("rent:rental_invoices", airport.identifier, rental_agreement.id)

    return redirect("rent:rental_invoices", airport.identifier, rental_agreement.id)


@require_airport_manager()
def update_rental_invoice(request, airport_identifier, rental_agreement_id):
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

    elif action == "finalize":
        if stripe_invoice_service.finalize_invoice(invoice.stripe_invoice.stripe_id):
            return render(request, tr_html,{"invoice": invoice})
        else:
            return HttpResponseForbidden()

    elif action == "cancel":
        if invoice_svc.cancel_invoice(invoice):
            return render(request, tr_html,{"invoice": invoice})
        else:
            return HttpResponseForbidden()

    elif action == "waive":
        if invoice_svc.waive_invoice(invoice):
            return render(request, tr_html, {"invoice": invoice})
        else:
            return HttpResponseForbidden()

    elif action == "paid":
        # A dollar amount may be specified for partial-payment
        amount_paid = request.POST.get("amount_paid")
        waive_remainder = request.POST.get("waive") == "Y"
        payment_method_code = request.POST.get("payment_method_code")

        # If waiving with no partial payment
        if waive_remainder and not amount_paid:
            if invoice_svc.waive_invoice(invoice):
                return render(request, tr_html, {"invoice": invoice})
            else:
                return HttpResponseForbidden()

        else:
            # Mark full or partial payment
            if not invoice_svc.pay_invoice(invoice, amount_paid, payment_method_code):
                return HttpResponseForbidden()

            # Waive remainder if requested to do so on an Open invoice
            if waive_remainder and invoice.status_code == "O":
                if not invoice_svc.waive_invoice(invoice):
                    return HttpResponseForbidden()

            return render(request, tr_html,{"invoice": invoice})


    elif action == "stripe":
        send_invoice = request.POST.get("send_invoice") == "Y"
        if invoice_svc.convert_to_stripe(invoice, send_invoice=send_invoice):
            return render(request, tr_html, {"invoice": invoice})
        else:
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
            if user:
                tenant = Tenant.objects.get(Q(user=user) | Q(contact=contact))
            else:
                tenant = Tenant.objects.get(contact=contact)
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

    # Get or create a Stripe customer for this RentalAgreement
    customer = AirportCustomer.get(airport, contact)
    if not customer:
        customer = StripeCustomer.get_or_create(
            full_name=tenant.display_name, email=tenant.email, user=tenant.user
        )

    # Create the rental record
    rental = None
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
        rental.set_new_series()
        rental.customer = customer
        rental.save()
        message_service.post_success("New tenant has been added")

        # If added via application, mark application as accepted
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
    metadata = {"rental_agreement"}

    if rental is None or issues:
        return redirect("infrastructure:hangar",airport_identifier, hangar.code)
    else:
        return redirect("rent:rental_invoices",airport_identifier, rental.id)


@report_errors()
@require_airport_manager()
def terminate_rental_agreement(request, airport_identifier):
    airport = request.airport
    rental_agreement_id = request.POST.get("rental_agreement_id")
    rental_agreement = RentalAgreement.get(rental_agreement_id) if rental_agreement_id else None
    if not rental_agreement:
        message_service.post_error("Unable to locate rental agreement.")
        return redirect("infrastructure:buildings", airport_identifier)

    agreement_svc.terminate_rental_agreement(rental_agreement)
    return redirect("infrastructure:hangar", airport_identifier, rental_agreement.hangar.code)