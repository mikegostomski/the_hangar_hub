from django.shortcuts import render, redirect
from base.services import utility_service, auth_service, message_service, date_service
from base.decorators import require_authority, require_authentication, require_feature
from base.models.utility.audit import Audit
from base.models import XssAttempt
from django.db.models import Q
from django.http import HttpResponseForbidden, Http404, HttpResponse
from django.core.paginator import Paginator
from base.classes.util.app_data import Log, EnvHelper, AppData
from base.classes.auth.session import Auth
from base.models.referral import Referral
from base.models.utility.variable import Variable

log = Log()
env = EnvHelper()

@require_authentication()
@require_feature("referrals")
def referral_dashboard(request):
    referral_codes = Referral.objects.filter(user=Auth.current_user())
    offer_you, offer_them, offer_details = Referral.reward_description()
    return render(
        request,
        'base/referral/dashboard.html',
        {
            "referral_codes": referral_codes,
            "offer_you": offer_you,
            "offer_them": offer_them,
            "offer_details": offer_details,
         }
    )

@require_authentication()
@require_feature("referrals")
def generate_referral_code(request):
    new_code = Referral()
    new_code.populate()
    new_code.save()

    return redirect("base:referral_dashboard")
