from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404, HttpResponseForbidden
from base.classes.util.env_helper import EnvHelper, Log
from base.classes.util.date_helper import DateHelper
from base.classes.auth.session import Auth
from base.services import utility_service, message_service, auth_service
from base.decorators import require_authority, report_errors
from base.models.utility.error import Error
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.db.models import Q
from datetime import timedelta

log = Log()
env = EnvHelper()
allowable_role_list = ["~super_user"]


@report_errors()
@require_authority(allowable_role_list)
def error_list(request):
    """
    Show errors encountered in this app
    """
    sort, page, error_filter = utility_service.pagination_sort_info(
        request, "date_created", "desc", "error_filter"
    )

    if not error_filter:
        app_errors = (
            Error.objects.exclude(status_code__in=["R", "I"])
        )
    else:
        app_errors = Error.objects

        for ww in error_filter.split():
            if ww and len(ww) > 2:

                # If keyword is a path
                if "/" in ww:
                    app_errors = app_errors.filter(path__icontains=ww)

                # Handle some specified properties
                elif ":" in ww:
                    pieces = ww.split(":")

                    # This could still be part of an error message
                    if len(pieces[1]) <= 2:
                        app_errors = app_errors.filter(
                            Q(error_friendly__icontains=ww)
                            | Q(error_system__icontains=ww)
                        )

                    # If date is expected
                    elif pieces[0].lower() in ["before", "after", "on", "since"]:
                        try:
                            cd = DateHelper(pieces[1])
                            if pieces[0].lower() == "before":
                                app_errors = app_errors.filter(
                                    date_created__lt=cd.datetime_instance
                                )
                            elif pieces[0].lower() in ["after", "since"]:
                                app_errors = app_errors.filter(
                                    date_created__gte=cd.datetime_instance
                                )
                            else:
                                next_day = cd.datetime_instance + timedelta(days=1)
                                app_errors = app_errors.filter(
                                    date_created__gte=cd.datetime_instance
                                )
                                app_errors = app_errors.filter(
                                    date_created__lt=next_day
                                )
                        except Exception as ee:
                            message_service.post_warning(
                                f"Could not determine date from '{pieces[1]}'"
                            )
                            log.debug(ee)
                    # If user is expected
                    elif pieces[0].lower() in [
                        "user",
                        "username",
                        "id",
                    ]:
                        user = Auth.lookup_user(pieces[1])
                        if user:
                            un = user.username
                            app_errors = app_errors.filter(
                                Q(user=user) | Q(auth_description__icontains=un)
                            )
                        else:
                            message_service.post_warning(f"{pieces[0]} not found")
                    else:
                        # Treat as part of the error, which may have contained a ':'
                        app_errors = app_errors.filter(
                            Q(error_friendly__icontains=ww)
                            | Q(error_system__icontains=ww)
                        )

                elif ww.isnumeric():
                    user = Auth.lookup_user(ww)
                    if user:
                        un = user.username
                        app_errors = app_errors.filter(
                            Q(user=user)
                            | Q(auth_description__icontains=un)
                        )
                    else:
                        app_errors = app_errors.filter(
                            Q(error_friendly__icontains=ww)
                            | Q(error_system__icontains=ww)
                        )

                # For all other keywords, look at error messages and usernames
                else:
                    app_errors = app_errors.filter(
                        Q(error_friendly__icontains=ww)
                        | Q(error_system__icontains=ww)
                        | Q(user__username=ww)
                    )

    # Sort results
    app_errors = app_errors.order_by(*sort)

    # Paginate the results
    paginator = Paginator(app_errors, 50)
    app_errors = paginator.get_page(page)

    status_options = {"N": "New", "I": "Ignored", "R": "Resolved", "W": "Watch"}

    return render(
        request,
        "base/error/list.html",
        {
            "app_errors": app_errors,
            "status_options": status_options,
            "error_filter": error_filter,
        },
    )


@report_errors()
@require_authority(allowable_role_list)
def error_status(request):
    """
    Set error status
    """
    if request.method == "POST":
        error_id = request.POST.get("error_id")
        new_status = request.POST.get("new_status")
        if error_id and new_status:
            ee = Error.objects.get(pk=int(error_id))
            ee.status_code = new_status
            ee.save()
            return HttpResponse(new_status)
    return HttpResponseForbidden()


@report_errors()
@require_authority(allowable_role_list)
def ignore_similar(request, error_id):
    """
    Set error status to ignored for all errors with the same message
    """
    try:
        error = Error.objects.get(pk=int(error_id))
        if error:
            posted_ee = error.error_friendly
            system_ee = error.error_system
            debug_info = error.debug_info

            errors = None
            ignored_errors = 0

            if system_ee:
                errors = Error.objects.filter(status_code="N", error_system=system_ee)
                if len(errors) <= 1:
                    errors = Error.objects.filter(
                        status_code="N", error_system__startswith=system_ee[:20]
                    )

            elif posted_ee:
                errors = Error.objects.filter(status_code="N", error_friendly=posted_ee)
                if len(errors) <= 1:
                    errors = Error.objects.filter(
                        status_code="N", error_friendly__startswith=posted_ee[:20]
                    )

            elif debug_info:
                errors = Error.objects.filter(status_code="N", debug_info=debug_info)
                if len(errors) <= 1:
                    errors = Error.objects.filter(
                        status_code="N", debug_info__startswith=debug_info[:20]
                    )

            if errors:
                for ee in errors:
                    ee.status_code = "I"
                    ee.save()
                    ignored_errors += 1

            if ignored_errors > 0:
                message_service.post_success(f"Ignored {ignored_errors} error{'' if ignored_errors == 1 else 's'}")
            else:
                message_service.post_warning("No errors were ignored")
        else:
            message_service.post_error("Error was not found. No errors were ignored.")

    except Exception as ee:
        Error.unexpected("Unable to ignore errors", ee)

    return redirect("base:errors")
