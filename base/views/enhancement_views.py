from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404, HttpResponseForbidden
from base.classes.util.env_helper import EnvHelper, Log
from base.classes.util.date_helper import DateHelper
from base.classes.auth.session import Auth
from base.services import utility_service, message_service, auth_service
from base.decorators import require_authority, report_errors, require_authentication
from base.models.utility.error import Error
from base.models.utility.enhancement_requests import EnhancementRequest, EnhancementVote
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.db.models import Q
from datetime import timedelta

log = Log()
env = EnvHelper()
allowable_role_list = ["~super_user"]


@report_errors()
@require_authentication()
def enhancement_requests(request):
    sort, page, enhance_filter = utility_service.pagination_sort_info(
        request, "date_created", "desc", "enhance_filter"
    )

    if not enhance_filter:
        enhancements = (
            EnhancementRequest.objects.exclude(status_code__in=["D", "C", "M"])
        )
    else:
        enhancements = EnhancementRequest.objects
        enhancements = enhancements.filter(
            Q(summary__icontains=enhance_filter) | Q(detail__icontains=enhance_filter)
        )

    # Sort results
    enhancements = enhancements.order_by(*sort)

    # Paginate the results
    paginator = Paginator(enhancements, 50)
    enhancements = paginator.get_page(page)

    return render(
        request,
        "base/enhancements/list.html",
        {
            "enhancements": enhancements,
            "enhance_filter": enhance_filter,
            "status_options": EnhancementRequest.status_options(),
            "request_type_options": EnhancementRequest.request_type_options(),
        },
    )


@report_errors()
@require_authentication()
def submit_enhancement_request(request):
    # Get parameters
    request_type_code = request.POST.get("request_type_code")
    summary = request.POST.get("summary")
    detail = request.POST.get("detail")
    prefill = {
        "request_type_code": request_type_code,
        "summary": summary,
        "detail": detail,
    }

    # RTC and Summary are required
    if not (request_type_code and summary):
        env.set_flash_scope("prefill", prefill)
        message_service.post_error("Request Type and Summary are required")
        return redirect("base:enhancement_requests")

    try:
        er = EnhancementRequest()
        er.user = Auth.current_user()
        er.status_code = "N"
        er.request_type_code = request_type_code
        er.summary = summary
        er.detail = detail
        er.save()
    except Exception as ee:
        message_service.post_error("Unable to save your request.")
        log.error(ee)
        env.set_flash_scope("prefill", prefill)


    return redirect("base:enhancement_requests")


@report_errors()
@require_authentication()
def enhancement_vote(request):
    # Get parameters
    enhancement_id = request.POST.get("enhancement_id")
    vote = request.POST.get("vote")
    log.trace([enhancement_id, vote])

    if not enhancement_id:
        return HttpResponseForbidden()

    if str(vote) not in ["1", "-1"]:
        message_service.post_error("Invalid vote value. Could not process your vote.")
        return HttpResponseForbidden()

    er = EnhancementRequest.get(enhancement_id)
    if not er:
        message_service.post_error("Enhancement not found. Could not process your vote.")
        return HttpResponseForbidden()

    try:
        # Look for previous vote to amend
        previous_vote = er.cu_vote()
        if previous_vote:
            previous_vote.value = vote
            previous_vote.save()
        else:
            ev = EnhancementVote()
            ev.user = Auth.current_user()
            ev.enhancement = er
            ev.value = vote
            ev.save()

        er = EnhancementRequest.get(enhancement_id)
        return render(request, "base/enhancements/_votes.html", {"er": er})

    except Exception as ee:
        message_service.post_error("Unable to save your vote.")
        log.error(ee)
    return HttpResponseForbidden()
