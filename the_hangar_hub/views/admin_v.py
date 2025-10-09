from django.shortcuts import render, redirect
from base.classes.util.env_helper import Log, EnvHelper
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.invitation import Invitation
from base.services import message_service
from base.decorators import require_authority, require_authentication, report_errors


log = Log()
env = EnvHelper()

@require_authority("developer")
def subscriptions(request):
    return render(
        request, "the_hangar_hub/admin/subscriptions/index.html",
        {
        }
    )








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
