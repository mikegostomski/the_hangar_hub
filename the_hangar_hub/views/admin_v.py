from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from base.classes.util.env_helper import Log, EnvHelper
from base.models.utility.error import Error
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.invitation import Invitation
from base.services import message_service
from base.decorators import require_authority, require_authentication, report_errors
from base_stripe.services import product_service
from base_stripe.models.product_models import StripePrice
import json


log = Log()
env = EnvHelper()

@require_authority("developer")
def products(request):
    return render(
        request, "the_hangar_hub/admin/products/index.html",
        {
            "products": product_service.get_products()
        }
    )

@require_authority("developer")
def price_visibility(request):
    try:
        price_id = request.POST.get("price_id")
        price = StripePrice.get(price_id)
        if not price:
            message_service.post_error("Unable to locate specified price")
            return HttpResponseForbidden()

        display = request.POST.get("new_visibility", "N") == "Y"
        log.info(f"Display price {price}: {display}")
        price.display = display
        price.save()
        return HttpResponse("ok")
    except Exception as ee:
        Error.unexpected("Unable to update price visibility", ee)
        return HttpResponseForbidden()

@require_authority("developer")
def price_trial_days(request):
    try:
        price_id = request.POST.get("price_id")
        price = StripePrice.get(price_id)
        if not price:
            message_service.post_error("Unable to locate specified price")
            return HttpResponseForbidden()

        if price.set_trial_days(request.POST.get("trial_days") or 0):
            return HttpResponse("ok")
    except Exception as ee:
        Error.unexpected("Unable to update price visibility", ee)
    return HttpResponseForbidden()


@require_authority("developer")
def update_price_attr(request):
    """
    Update aspects of the price not saved in Stripe
        - Visibility
        - Featured
        - Badge
        - Feature List
    """
    attr = request.POST.get("attr")
    val = request.POST.get("value")
    if not attr:
        message_service.post_error("Invalid request")
        return HttpResponseForbidden()

    if attr == "features":
        # Must be valid JSON string
        if not val:
            val = None
        else:
            log.debug("Loading JSON")
            try:
                val = json.loads(val)
                log.debug(f"Value: {val}")
            except:
                message_service.post_error("Features must be a valid JSON list format")
                return HttpResponseForbidden()
    elif attr == "featured":
        val = val == "Y"

    try:
        price_id = request.POST.get("price_id")
        price = StripePrice.get(price_id)
        if not price:
            message_service.post_error("Unable to locate specified price")
            return HttpResponseForbidden()

        log.info(f"Update {price}: {attr} = {val}")
        setattr(price, attr, val)
        price.save()
        return HttpResponse("ok")
    except Exception as ee:
        Error.unexpected(f"Unable to update price {attr}", ee)
        return HttpResponseForbidden()





@report_errors()
@require_authority("developer")
def invitation_dashboard(request):
    open_invitations = Invitation.objects.filter(status_code__in=["I", "S"])


    return render(
        request, "the_hangar_hub/admin/invitations/dashboard.html",
        {
            "open_invitations": open_invitations,
            "Invitation": Invitation,
            "prefill": env.get_flash_scope("prefill")
        }
    )


@report_errors()
@require_authority("developer")
def send_invitation(request):

    airport_identifier = request.POST.get("airport")
    email = request.POST.get("email")
    role_code = request.POST.get("role_code")
    prefill = {"airport": airport_identifier, "email": email, "role_code": role_code}
    if not (airport_identifier or email or role_code):
        # Accidental submission (no error message needed)
        return redirect("dev:invitation_dashboard")
    if not (airport_identifier and email and role_code):
        message_service.post_error(f"Airport, Email, and Role are all required fields")
        env.set_flash_scope("prefill", prefill)
        return redirect("dev:invitation_dashboard")

    airport = Airport.get(airport_identifier)
    if not airport:
        suggestions = Airport.objects.filter(identifier__icontains=airport_identifier)
        ss = f"<br> bi-lightbulb Did you mean: {', '.join([x.identifier for x in suggestions])}" if suggestions else ""
        message_service.post_error(f"bi-exclamation-triangle Airport identifier not found: {airport_identifier}{ss}")
        env.set_flash_scope("prefill", prefill)
        return redirect("dev:invitation_dashboard")

    if Invitation.invite_manager(airport, email):
        message_service.post_success("Invitation sent!")
    else:
        env.set_flash_scope("prefill", prefill)
        message_service.post_error("Invitation was not sent.")

    return redirect("dev:invitation_dashboard")
