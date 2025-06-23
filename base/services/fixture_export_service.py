# fixture_export_service.py
#
#   Functions used when exporting database tables to YAML files
#   for use as Django fixtures
#

from django.http import HttpResponse
from base.classes.util.env_helper import EnvHelper, Log
from base.classes.auth.session import Auth
import sys
import inspect
from django.db import models
from django.core import serializers
from django.apps import apps

log = Log()
env = EnvHelper()
allowable_role_list = "developer"

def _short_app_name(app):
    if "." in app:
        p = app.split(".")
        return p[len(p)-1]
    return app

def get_exportable_apps():
    # Get a list of apps to export models for
    installed_apps = env.get_setting("INSTALLED_APPS")
    exportable_apps = []

    for aa in installed_apps:
        # Never export data from certain non-base apps
        if aa.startswith('django.contrib') and aa != "django.contrib.auth":
            continue
        if aa in ["crequest", "sass_processor", "corsheaders"]:
            continue

        exportable_apps.append(aa)

    return exportable_apps


def get_exportable_models():
    """
    Get list of models grouped by app_name

    Returns: {"<app_name">: [ "<model_name>", ... ]}
    """

    # Get a list of models from each app
    app_models = {}
    for app_name in get_exportable_apps():
        log.info(f"Getting models for: {app_name}")
        app_models[app_name] = []
        try:
            model_list = inspect.getmembers(
                sys.modules[f"{app_name}.models"], inspect.isclass
            )
            log.info(f"Potential models: {model_list}")
            for mm in model_list:
                try:
                    model_name = mm[0]

                    # User is the only model we want from auth
                    if app_name == "django.contrib.auth" and model_name != "User":
                        continue

                    log.info(f"Getting details for: {app_name}")
                    this_model = apps.get_model(
                        _short_app_name(app_name),
                        model_name
                    )
                    if issubclass(this_model, models.Model):
                        app_models[app_name].append(model_name)
                except Exception as ee:
                    log.info(f"{mm} is not a model. Error: {ee}")
        except Exception as ee:
            log.warning(f"Unable to export from {app_name}: {ee}")

    log.info(f"Exportable Models: {app_models}")
    return app_models


def get_exportable_model_count():
    """
    Get list of models and how many records they contain; Grouped by app_name

    Returns: {"<app_name">: [ ("<model_name>", num_records), ... ]}
    """
    model_data = {}
    for app_name, model_names in get_exportable_models().items():
        model_data[app_name] = []

        for model_name in model_names:
            exportable_model = apps.get_model(_short_app_name(app_name), model_name)
            num_records = exportable_model.objects.count()
            model_data[app_name].append((model_name, num_records))

    return model_data


def export_models(app_models, since_date=None):
    # Export models to a file
    response = HttpResponse(content_type="text/plain")
    response["Content-Disposition"] = 'attachment; filename="model_export.yaml"'
    yaml_serializer = serializers.get_serializer("yaml")
    yaml_serializer = yaml_serializer()
    # with open("file.yaml", "w") as out:

    if since_date:
        log.info(f"Exporting records since {since_date}")

    for app_name, model_list in app_models.items():
        response.write(f"# APPLICATION: {app_name}\n")
        response.write(f"# {'#'*80}\n")
        for model_name in model_list:
            response.write(f"\n# MODEL: {app_name}.{model_name.lower()}\n")
            response.write(f"# {'='*60}\n")
            exportable_model = apps.get_model(_short_app_name(app_name), model_name)
            if since_date and hasattr(exportable_model, "date_created"):
                num_records = exportable_model.objects.filter(date_created__gte=since_date).count()
            else:
                num_records = exportable_model.objects.count()

            if num_records == 0:
                log.info(f"Nothing to export in {app_name}.{model_name}")
                response.write(f"# No data in {app_name}.{model_name}\n")
            else:
                log.info(f"Exporting {num_records} from {app_name}.{model_name}")
                if since_date and hasattr(exportable_model, "date_created"):
                    export_objects = exportable_model.objects.filter(date_created__gte=since_date)
                else:
                    export_objects = exportable_model.objects.all()

                yaml_serializer.serialize(export_objects, stream=response)
                Auth.audit("R", "EXPORT", comments=f"{app_name}.{model_name} exported to yaml file")

    return response
