# audit_views.py
#
#   These are views that are used for auditing events
#

from django.shortcuts import render
from ..services import utility_service, auth_service, message_service, date_service
from ..decorators import require_authority
from base.models.utility.audit import Audit
from base.models import XssAttempt
from django.db.models import Q
from django.http import HttpResponseForbidden, Http404, HttpResponse
from django.core.paginator import Paginator
from base.classes.util.app_data import Log, EnvHelper, AppData
from base.classes.auth.session import Auth

log = Log()
env = EnvHelper()

allowable_role_list = ['~security']

@require_authority(allowable_role_list)
def audit_list(request):
    """
    List audit events
    """
    # Get a list of all audit event codes (for filtering)
    event_codes = Audit.objects.values("event_code").distinct()

    crud_options = {"C": "Create", "R": "Read", "U": "Update", "D": "Delete"}

    app = AppData()
    sub_apps = app.sub_apps() if auth_service.has_authority("developer") else None
    if sub_apps:
        # Main app needs to be added to the list
        p_app = app.get_primary_app_code()
        p_name = env.get_setting("APP_NAME")
        all_apps = {"%": "All Apps", p_app: p_name}
        all_apps.update(sub_apps)
        sub_apps = all_apps
        del all_apps

    # Initialize filter variables
    ff = {
        "app_code": "%" if sub_apps else app.get_app_code(),
        "username": None,
        "sso": None,
        "impersonated": None,
        "proxied": None,
        "from_date": None,
        "to_date": None,
        "from_date_display": None,
        "to_date_display": None,
        "crud_code": None,
        "event_code": None,
        "reference": None,
        "comment": None,
        "hide_logins": None,
    }
    user_instance = None

    # Were filters updated/submitted?
    if request.GET.get("filter_submission"):

        # Get user filters
        ff["username"] = request.GET.get("username_filter")
        user_types = request.GET.getlist("user_type")
        if user_types:
            ff["sso"] = "S" in user_types
            ff["impersonated"] = "I" in user_types
            ff["proxied"] = "P" in user_types

        # Provide default if user_type of none selected
        if not any([ff["sso"], ff["impersonated"], ff["proxied"]]):
            # Select all by default
            ff["sso"] = ff["impersonated"] = ff["proxied"] = True

        # Get date filters
        ff["from_date"] = request.GET.get("from_date")
        ff["to_date"] = request.GET.get("to_date")

        # Get event filter
        ff["crud_code"] = request.GET.getlist("crud_code")
        ff["event_code"] = request.GET.getlist("event_code")
        ff["hide_logins"] = request.GET.getlist("hide_logins")

        # Get reference filter
        ff["reference"] = request.GET.get("reference")

        # Get comment filter
        ff["comment"] = request.GET.get("comment")

        # Get app_code filter (developers only)
        app_code = app.get_app_code()
        if sub_apps and auth_service.has_authority("developer"):
            app = request.GET.get("app_code", "%")
            if app == "%" or app in sub_apps:
                app_code = app
        ff["app_code"] = app_code

        # Save selections for future requests (pagination)
        env.set_session_variable("audit_filter_selections", ff)

    # Otherwise, look for saved filters
    else:
        ff = env.get_session_variable("audit_filter_selections", ff)

    # Get convenient date instances
    from_date_instance = date_service.string_to_date(ff["from_date"])
    to_date_instance = date_service.string_to_date(ff["to_date"])

    # Get pagination data from session and/or params
    sortby, page, ff["comment"] = utility_service.pagination_sort_info(
        request, "date_created", "desc", filter_name="comment"
    )

    # Start building the query
    # ========================

    # App code may be selected by developers for an app with sub-apps
    app_code = ff["app_code"]
    if app_code == "%":
        # Select from all sub-apps (app_code is never null)
        audits = Audit.objects.select_related("user").select_related("impersonated_user").select_related("proxied_user").filter(Q(app_code__isnull=False))
    else:
        audits = Audit.objects.select_related("user").select_related("impersonated_user").select_related("proxied_user").filter(Q(app_code=app_code))

    if ff["username"]:
        # Get the user
        query_user = ff["username"]
        targets = f"{'A' if ff['sso'] else '-'}{'I' if ff['impersonated'] else '-'}{'P' if ff['proxied'] else '-'}"

        # Only one user-type selected
        if targets == "A--":
            audits = audits & Audit.objects.filter(Q(user__username=query_user))
        elif targets == "-I-":
            audits = audits & Audit.objects.filter(Q(impersonated_user__username=query_user))
        elif targets == "--P":
            audits = audits & Audit.objects.filter(Q(proxied_user__username=query_user))
        # Two user-types selected
        elif targets == "AI-":
            audits = audits & Audit.objects.filter(Q(user__username=query_user)|Q(impersonated_user__username=query_user))
        elif targets == "A-P":
            audits = audits & Audit.objects.filter(Q(user__username=query_user)|Q(proxied_user__username=query_user))
        elif targets == "-IP":
            audits = audits & Audit.objects.filter(Q(impersonated_user__username=query_user)|Q(proxied_user__username=query_user))
        # Three user-types selected
        elif targets == "AIP":
            audits = audits & Audit.objects.filter(Q(user__username=query_user)|Q(impersonated_user__username=query_user)|Q(proxied_user__username=query_user))


    if ff["from_date"]:
        # Must be in proper timestamp format (with hours and minutes)
        audits = audits & Audit.objects.filter(Q(date_created__gte=from_date_instance))

    if ff["to_date"]:
        # Must be in proper timestamp format (with hours and minutes)
        audits = audits & Audit.objects.filter(Q(date_created__lte=to_date_instance))

    if ff["crud_code"]:
        empty_list = str(ff["crud_code"]) == "['']"
        if not empty_list:
            audits = audits & Audit.objects.filter(
                Q(crud_code__in=ff["crud_code"])
            )
        else:
            ff["crud_code"] = None

    if ff["event_code"]:
        empty_list = str(ff["event_code"]) == "['']"
        if not empty_list:
            audits = audits & Audit.objects.filter(
                Q(event_code__in=ff["event_code"])
            )
        else:
            ff["event_code"] = None

    if ff["hide_logins"]:
        audits = audits & Audit.objects.exclude(Q(event_code="LOGIN"))

    if ff["reference"]:
        for ww in ff["reference"].split():
            if ww.isnumeric():
                q = Q(reference_id=ww)
            else:
                q = Q(reference_code__icontains=ww)
            audits = audits & Audit.objects.filter(q)

    if ff["comment"]:
        audits = audits & Audit.objects.filter(Q(comments__icontains=ff["comment"]))

    # Get sort, order, and page
    audits = audits.order_by(*sortby)

    paginator = Paginator(audits, 50)
    audits = paginator.get_page(page)

    return render(
        request,
        "base/audit/list.html",
        {
            "audits": audits,
            "ff": ff,
            "user_instance": user_instance,
            "event_codes": {
                result["event_code"]: result["event_code"] for result in event_codes
            },
            "crud_options": crud_options,
            "from_date_instance": from_date_instance,
            "to_date_instance": to_date_instance,
            "sub_apps": sub_apps,
        },
    )


@require_authority(allowable_role_list)
def audit_xss_attempts(request):
    """
    List XSS attempts
    """
    sort, page = utility_service.pagination_sort_info(request, 'date_created', 'desc')

    # Get a list of all XSS attempts
    xss = XssAttempt.objects.filter(reviewer__isnull=True).order_by(*sort)
    paginator = Paginator(xss, 50)
    xss = paginator.get_page(page)

    return render(
        request, 'audit/xss_review.html',
        {
            'xss': xss,
        }
    )


@require_authority(allowable_role_list)
def audit_xss_review_attempt(request):
    """
    Review an XSS attempt
    """
    # Mark as reviewed
    xss_id = request.POST.get("id", 0)
    xss_instance = get_xss(xss_id)
    if xss_instance:
        xss_instance.reviewer_username = Auth.current_user_profile().username
        xss_instance.save()

        # Also log it in the audit table.
        Auth.audit("U", "XSS", comments=f"Reviewed attempt #{xss_id} by {xss_instance.user_username}")

        return HttpResponse("success")
    else:
        return HttpResponseForbidden()


def get_xss(xss_id):
    """
    Get xss from the given ID for the purpose of editing.
    Validate appropriate permissions to edit the xss
    """
    log.trace()

    auth = auth_service.get_auth_instance()

    # Get targeted xss
    xss_instance = XssAttempt.get(xss_id)
    if not xss_instance:
        message_service.post_error("XSS attempt not found")
        return None

    # Cannot review your own XSS
    if xss_instance.user_username:
        # Check both authenticated and impersonated users
        is_self = xss_instance.user_username == auth.authenticated_user.username
        is_self = is_self or xss_instance.user_username == auth.impersonated_user.username
        if is_self:
            message_service.post_error("You cannot review your own XSS attempts")
            return None

    # Otherwise, return the xss
    return xss_instance


def xss_prevention(request):
    return render(
        request,
        'base/audit/xss_block.html',
        {'path': request.path}
    )


def xss_lock(request):
    return render(
        request,
        'base/audit/xss_lock.html',
        {}
    )
