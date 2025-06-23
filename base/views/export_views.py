#
#   Used for exporting data from AWS database into fixtures for development instances
#
from django.shortcuts import render, redirect
from base.decorators import require_authority
from django.http import HttpResponse, JsonResponse
from base.classes.util.env_helper import Log, EnvHelper
from base.services import message_service, fixture_export_service
import sys
import inspect
from django.db import models
from django.core import serializers
from django.apps import apps

log = Log()
env = EnvHelper()
allowable_role_list = ["developer"]


@require_authority(allowable_role_list)
def fixture_export_menu(request):
    """
    Select models to export to JSON files
    """
    app_models = fixture_export_service.get_exportable_model_count()
    return render(request, "base/fixture_export/menu.html", {"app_models": app_models})


@require_authority(allowable_role_list)
def fixture_export_action(request):
    """
    Select models to export to JSON files
    """
    selections = request.POST.getlist("app_model")
    if not selections:
        message_service.post_error("You must select some models to export")
        return redirect("psu:export")

    # Allow selecting records since specified date
    # (when there are too many records to export, resulting in an out-of-memory error)
    since_date = request.POST.get("since_date")
    if since_date:
        since_date = ConvenientDate(since_date).datetime_instance

    app_models = {}
    for selection in selections:
        if "|" not in selection:
            message_service.post_error("Invalid selection!")
            return redirect("psu:export")

        x = selection.split("|")
        app_name = x[0]
        model_name = x[1]

        if app_name not in app_models:
            app_models[app_name] = []

        app_models[app_name].append(model_name)

    return fixture_export_service.export_models(app_models, since_date)

#

@require_authority('developer')
def export_db(request):
    pass

#     """
#     Export all model instances
#     """
#     # Get a list of apps to export models for
#     installed_apps = env.get_setting('INSTALLED_APPS')
#     exportable_apps = []
#     for aa in installed_apps:
#         if aa.startswith('django.contrib') and aa != "django.contrib.auth":
#             continue
#         if aa in ['django_cas_ng', 'crequest', 'sass_processor']:
#             continue
#         if 'allauth' in aa:
#             continue
#         exportable_apps.append(aa)
#     log.info(f"Exportable apps: {exportable_apps}")
#
#     # Get a list of models from each app
#     app_models = {}
#     for app_name in exportable_apps:
#         log.info(f"Getting models for: {app_name}")
#         app_models[app_name] = []
#         model_list = inspect.getmembers(sys.modules[f'{app_name}.models'], inspect.isclass)
#         log.info(f"Potential models: {model_list}")
#         for mm in model_list:
#             try:
#                 model_name = mm[0]
#                 if app_name == "django.contrib.auth" and model_name != "User":
#                     continue
#                 log.info(f"Getting details for: {app_name}")
#                 this_model = apps.get_model(
#                     "auth" if app_name == "django.contrib.auth" else app_name,
#                     model_name
#                 )
#                 if issubclass(this_model, models.Model):
#                     app_models[app_name].append(model_name)
#             except Exception as ee:
#                 log.info(f"Not a model: {mm} ({ee})")
#     log.info(f"Models to be exported: {app_models}")
#
#     # Export models to a file
#     response = HttpResponse(content_type='text/plain')
#     response['Content-Disposition'] = 'attachment; filename="model_export.yaml"'
#     YAMLSerializer = serializers.get_serializer("yaml")
#     yaml_serializer = YAMLSerializer()
#     # with open("file.yaml", "w") as out:
#     for app_name, model_list in app_models.items():
#         for model_name in model_list:
#             ExportableModel = apps.get_model("auth" if app_name == "django.contrib.auth" else app_name, model_name)
#             yaml_serializer.serialize(ExportableModel.objects.all(), stream=response)
#
#     # auth_service.audit_event('EXPORT', comments="Database exported to yaml file")
#     return response
