from base.classes.util.app_data import Log, EnvHelper, AppData
from base.classes.auth.session import Auth
from the_hangar_hub.services import airport_service, tenant_s, application_service


log = Log()
env = EnvHelper()
app = AppData()


def airport_data(request):
    if request.path.startswith("/accounts/"):
        return {}

    managed_airports = airport_service.managed_airports()
    rentals = tenant_s.get_rental_agreements(Auth.current_user())
    open_applications = application_service.get_active_applications()
    selected_application = application_service.get_selected_application()
    airport = request.airport if hasattr(request, "airport") else None

    # Airport-specific data when an airport is selected
    is_airport_manager = is_airport_tenant = False
    if airport:
        if managed_airports:
            is_airport_manager = airport in managed_airports
        if rentals:
            is_airport_tenant = airport in [x.hangar.building.airport for x in rentals]

    model = {
        "airport": airport,
        "is_a_manager": bool(managed_airports),
        "is_airport_manager": is_airport_manager,
        "is_a_tenant": bool(rentals),
        "is_airport_tenant": is_airport_tenant,
        "managed_airports": managed_airports,
        "my_rentals": rentals,
        "open_applications": len(open_applications),
        "selected_application": selected_application,
    }
    return model

