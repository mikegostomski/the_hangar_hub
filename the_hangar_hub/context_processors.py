from base.classes.util.app_data import Log, EnvHelper, AppData
from base.classes.auth.session import Auth
from the_hangar_hub.services import airport_service, tenant_s, application_service
from the_hangar_hub.models.airport import Amenity


log = Log()
env = EnvHelper()
app = AppData()


def airport_data(request):
    if request.path.startswith("/accounts/"):
        return {}

    # Most pages will require an airport, and have features for either managers or tenants
    airport = request.airport if hasattr(request, "airport") else None

    # Manager/Tenant role specific to THIS airport (False if no airport selected)
    manages_this_airport = request.manages_this_airport if hasattr(request, "manages_this_airport") else False
    based_at_this_airport = request.based_at_this_airport if hasattr(request, "based_at_this_airport") else False

    # If a manager manages multiple airports, there will be admin links for each airport in the nav bar
    managed_airports = airport_service.managed_airports()

    # If a tenant has multiple hangars, maybe at multiple airports, they'll see links for each in their navbar
    # Check this even if not a tenant, as there could be past rental agreements
    rentals = tenant_s.get_rental_agreements(Auth.current_user())

    # If unsubmitted application exists, there will be reminders to complete it
    open_applications = application_service.get_active_applications()

    # If an airport manager selected an application to assign a hangar to...
    selected_application = application_service.get_selected_application()

    amenity_reviews = 0
    if Auth.current_user_profile().has_authority("developer"):
        amenity_reviews = Amenity.objects.filter(approved=False).count()

    model = {
        "airport": airport,
        "is_a_manager": bool(managed_airports),
        "manages_this_airport": manages_this_airport,
        "is_a_tenant": bool(rentals),
        "based_at_this_airport": based_at_this_airport,
        "managed_airports": managed_airports,
        "my_rentals": rentals,
        "open_applications": len(open_applications),
        "selected_application": selected_application,
        "amenity_reviews": amenity_reviews,
    }
    return model

