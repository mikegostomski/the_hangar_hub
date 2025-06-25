from django.shortcuts import render
from django.shortcuts import redirect
from base.services import date_service, message_service
from base.decorators import require_authority
from base.models import Feature
from django.http import HttpResponseForbidden, HttpResponse
from base.classes.util.log import Log
from datetime import datetime, timezone
from base.models.utility.error import Error

log = Log()
allowable_role_list = ['~superuser']


@require_authority(allowable_role_list)
def feature_list(request):
    """
    List all features for this application
    """
    # Current status of each feature
    toggle_status = Feature.get_feature_toggles()

    # Get all features
    features = Feature.objects.all()

    return render(
        request, 'base/features/list.html',
        {
            'features': features,
            'status_options': {'N': 'Disabled', 'Y': 'Enabled', 'L': 'Limited', },
            'now': datetime.now(timezone.utc),
            'toggle_status': toggle_status,
        }
    )


@require_authority(allowable_role_list)
def add_feature(request):
    # ToDo: Add features via AJAX calls
    log.trace()
    try:
        feature_code = request.POST.get('feature_code')
        if not feature_code:
            message_service.post_error("Feature code is required")
            return redirect('base:features')

        if Feature.get(feature_code):
            message_service.post_error("That feature code already exists")
            return redirect('base:features')

        nf = Feature()
        nf.feature_code = request.POST.get('feature_code')
        nf.feature_title = request.POST.get('feature_title')
        nf.feature_description = request.POST.get('feature_description')
        nf.status = request.POST.get('status')

        enable_date_str = request.POST.get('enable_date')
        nf.enable_date = date_service.string_to_date(enable_date_str)
        if enable_date_str and not nf.enable_date:
            message_service.post_error("Invalid activation date was given")

        disable_date_str = request.POST.get('disable_date')
        nf.disable_date = date_service.string_to_date(disable_date_str)
        if disable_date_str and not nf.disable_date:
            message_service.post_error("Invalid termination date was given")

        group_code = request.POST.get('group_code')
        if group_code:
            nf.group_code = group_code

        nf.save()
    except Exception as ee:
        Error.unexpected("Unable to create new feature", ee)
    return redirect('base:features')


@require_authority(allowable_role_list)
def modify_feature(request):
    log.trace()
    has_error = False

    # Get targeted feature
    feature_id = request.POST.get('id')
    feature_instance = Feature.get(feature_id)

    prop = request.POST.get('prop')
    value = request.POST.get('value')
    log.info(f"Change {prop} to {value}")

    if prop == 'title':
        value = value[:80] if value else feature_instance.feature_code
        feature_instance.feature_title = value
        feature_instance.save()
    if prop == 'group_code':
        value = value[:80] if value else None
        feature_instance.group_code = value
        feature_instance.save()
    elif prop == 'description':
        value = value[:500] if value else value
        feature_instance.feature_description = value
        feature_instance.save()
    elif prop == 'status':
        if value not in ['Y', 'N', 'L']:
            return HttpResponseForbidden("Invalid status was given")
        else:
            feature_instance.status = value
            feature_instance.save()
    elif prop.endswith('_date'):
        value = date_service.string_to_date(value)
        setattr(feature_instance, prop, value)
        feature_instance.save()
    else:
        return HttpResponseForbidden("Invalid property was selected")

    return HttpResponse(value)


@require_authority(allowable_role_list)
def delete_feature(request):
    log.trace()

    # Get targeted feature
    feature_id = request.POST.get('id')
    feature_instance = Feature.get(feature_id)
    feature_instance.delete()
    return HttpResponse('success')
