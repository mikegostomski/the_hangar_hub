from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from base_infotext.models import Infotext
from base.classes.util.log import Log
from base.services import utility_service, message_service
from base.decorators import require_authority
from django.db.models import Q
from collections import OrderedDict
from base.models.utility.error import Error

log = Log()

# ToDo: Error Handling/Messages


@require_authority(["admin", "infotext", "developer"])
def infotext_index(request):
    """
    Search page for locating infotext to be edited
    """
    log.trace()
    keywords = request.GET.get("keywords")

    text_instances = Infotext.objects.filter(app_code=utility_service.get_app_code())
    if keywords:
        text_instances = text_instances.filter(
            Q(text_code__icontains=keywords)
            | Q(content__icontains=keywords)
            | Q(group_title__icontains=keywords)
        )
    text_instances = text_instances.order_by("group_title", "text_code")

    # Group results by group_title
    results = OrderedDict()
    ungrouped = []
    if text_instances:
        for ii in text_instances:
            if ii.group_title:
                if ii.group_title in results:
                    results[ii.group_title].append(ii)
                else:
                    results[ii.group_title] = [ii]
            else:
                ungrouped.append(ii)

    if results and ungrouped:
        results["Other Infotext"] = ungrouped
    elif ungrouped:
        results["Infotext"] = ungrouped

    # Allow a page to direct a user here to edit a value, and provide a return URL (relative URLs only)
    return_address = request.GET.get("return")
    if return_address and not return_address.startswith("/"):
        return_address = None

    return render(
        request,
        "base_infotext/index.html",
        {
            "results": results,
            "keywords": keywords,
            "return_address": return_address,
        },
    )


@require_authority(["admin", "infotext", "developer"])
def infotext_update(request):
    """
    Update a given infotext instance
    """
    text_id = request.POST.get("id")
    text_content = request.POST.get("content")
    log.trace([text_id])

    text_instance = get_object_or_404(Infotext, pk=text_id)
    try:
        text_instance.set_content(text_content)
        text_instance.save()
        return HttpResponse(text_instance.content)
    except Exception as ee:
        Error.unexpected("Unable to save infotext", ee)
        return HttpResponseForbidden()


@require_authority(["admin", "infotext", "developer"])
def infotext_delete(request):
    """
    Delete a given infotext instance
    """
    text_id = request.POST.get("id")
    log.trace([text_id])
    text_instance = Infotext.get(text_id)
    if text_instance:
        text_instance.delete()
        message_service.post_success("Infotext deleted")
        return HttpResponse("Success")
    else:
        message_service.post_error("Infotext could not be located")
        return HttpResponseForbidden()


@require_authority(["admin", "infotext", "developer"])
def infotext_update_group(request):
    """
    Update a given infotext instance's group
    """
    text_id = request.POST.get("id")
    log.trace([text_id])
    text_instance = Infotext.get(text_id)
    if text_instance:
        text_instance.group_title = request.POST.get("group_title")
        text_instance.save()
        message_service.post_success("Infotext updated")
        return HttpResponse("Success")
    else:
        message_service.post_error("Infotext could not be located")
        return HttpResponseForbidden()
