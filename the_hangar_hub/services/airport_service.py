from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.auth import Auth
from base.services import auth_service
from the_hangar_hub.models.airport_manager import AirportManager

log = Log()
env = EnvHelper()

def get_managers(airport=None, status=None):
    managers = AirportManager.objects.filter(airport=airport)
    if status:
        managers = managers.filter(status=status)
    managers = managers.select_related("airport", "user")
    return managers

def is_airport_manager(user=None, airport=None):
    user_profile = Auth().lookup_user(user_data=user, get_authorities=True) if user else Auth().get_user()
    manages = AirportManager.objects.filter(user=user_profile.django_user(), status="A")
    if airport:
        manages = manages.filter(airport=airport)
    return manages.exists()

def set_airport_manager(airport, user=None):
    user_profile = Auth().lookup_user(user_data=user, get_authorities=True) if user else Auth().get_user()
    if not user_profile.is_valid():
        log.error(f"Cannot make invalid user an Airport Manager. ({user_profile})")
        return

    # Look for existing management relation (may not be active)
    try:
        existing = AirportManager.objects.get(user=user_profile.django_user(), airport=airport)
    except AirportManager.DoesNotExist:
        existing = None

    if existing:
        existing.status = "A"
        existing.save()
        Auth.audit(
            "U", "MANAGEMENT",
            "Activated airport manager relationship",
            reference_code="AirportManager", reference_id=existing.id
        )
    else:
        airport.management.create(user=user_profile.django_user(), airport=airport)
        Auth.audit(
            "C", "MANAGEMENT",
            "Created airport manager relationship",
            reference_code="AirportManager", reference_id=existing.id
        )

def deactivate_airport_manager(airport, user):
    log.trace([airport, user])
    try:
        user_profile = Auth().lookup_user(user_data=user)
        manager = AirportManager.objects.get(user=user_profile.django_user(), airport=airport)
        manager.status = "I"
        manager.save()
        Auth.audit(
            "U", "MANAGEMENT",
            "Deactivated airport manager relationship",
            reference_code="AirportManager", reference_id=manager.id
        )
    except AirportManager.DoesNotExist:
        log.debug("Could not find airport manager for removal")
    except Exception as ee:
        log.error(f"Could not remove airport manager: {ee}")
