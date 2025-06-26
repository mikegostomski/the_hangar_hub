from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404, HttpResponseForbidden
from base.classes.util.env_helper import EnvHelper, Log
from base.classes.util.date_helper import DateHelper
from base.classes.auth.session import Auth
from base.services import utility_service, message_service, auth_service
from base.decorators import require_authority, report_errors, require_authentication
from base.models.utility.error import Error
from base.models.utility.enhancement_requests import EnhancementRequest
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.db.models import Q
from datetime import timedelta

log = Log()
env = EnvHelper()
allowable_role_list = ["~super_user"]


@report_errors()
@require_authentication(allowable_role_list)
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
        },
    )

