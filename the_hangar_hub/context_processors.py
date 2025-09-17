from base.classes.util.app_data import Log, EnvHelper, AppData
from the_hangar_hub.services import airport_service, tenant_service, application_service
from the_hangar_hub.services import stripe_s
from base_stripe.services import webhook_service

log = Log()
env = EnvHelper()
app = AppData()


def airport_data(request):
    if request.path.startswith("/accounts/"):
        return {}

    # Some actions require immediate reaction to an expected Stripe action
    # In those cases, don't wait for the scheduled reaction... do it now.
    if stripe_s.webhook_reaction_needed():
        log.info("Need to react to Stripe events")
        webhook_service.react_to_events()

    managed_airports = airport_service.managed_airports()
    rentals = tenant_service.get_tenant_rentals()
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

