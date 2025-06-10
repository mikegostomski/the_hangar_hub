from base.services import utility_service, auth_service
from base.classes.breadcrumb import Breadcrumb
from django.conf import settings
from base.classes.util.app_data import Log, EnvHelper, AppData
from datetime import datetime, timezone
from the_hangar_hub.services import airport_service

log = Log()
env = EnvHelper()
app = AppData()


def airport(request):
    if request.path.startswith("/accounts/"):
        return {}

    log.trace()

    model = {
        "managed_airport_identifiers": airport_service.managed_airport_identifiers(),
    }


    return model

