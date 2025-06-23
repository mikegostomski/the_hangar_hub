from base.services import utility_service, auth_service
from base.classes.breadcrumb import Breadcrumb
from django.conf import settings
from base.classes.util.app_data import Log, EnvHelper, AppData
from datetime import datetime, timezone
from the_hangar_hub.services import airport_service, tenant_service, application_service
from base.classes.auth.session import Auth

log = Log()
env = EnvHelper()
app = AppData()


def airport(request):
    if request.path.startswith("/accounts/"):
        return {}

    managed_airports = airport_service.managed_airports()
    rentals = tenant_service.get_tenant_rentals()
    open_applications = application_service.get_active_applications()

    model = {
        "is_a_manager": bool(managed_airports),
        "is_a_tenant": bool(rentals),
        "managed_airports": managed_airports,
        "my_rentals": rentals,
        "open_applications": len(open_applications),
    }

    return model

