from base.services import utility_service, auth_service
from base.classes.breadcrumb import Breadcrumb
from django.conf import settings
from base.classes.util.app_data import Log, EnvHelper, AppData
from datetime import datetime, timezone
from the_hangar_hub.services import airport_service, tenant_service

log = Log()
env = EnvHelper()
app = AppData()


def airport(request):
    if request.path.startswith("/accounts/"):
        return {}

    managed_airports = airport_service.managed_airport_identifiers()
    rentals = tenant_service.get_tenant_rentals()

    model = {
        "is_manager": bool(managed_airports),
        "is_tenant": bool(rentals),
        "managed_airport_identifiers": managed_airports,
        "my_rentals": rentals,
    }


    return model

