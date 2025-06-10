from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.auth import Auth
from the_hangar_hub.models.airport_manager import AirportManager
from the_hangar_hub.models.invitation import Invitation


log = Log()
env = EnvHelper()


def can_query_user(user_profile):
    """
    Can only run queries with related User field when the specified User object has been saved
    """
    return user_profile.django_user().id

def get_managers(airport=None, status=None):
    managers = AirportManager.objects.filter(airport=airport)
    if status:
        managers = managers.filter(status_code=status)
    managers = managers.select_related("airport", "user")
    return managers

def is_airport_manager(user=None, airport=None):
    user_profile = Auth().lookup_user(user_data=user) if user else Auth().get_user()
    if can_query_user(user_profile):
        manages = AirportManager.objects.filter(user=user_profile.django_user(), status_code="A").select_related("user")
        if airport:
            manages = manages.filter(airport=airport)
        return bool([mgmt for mgmt in manages if mgmt.is_active])
    else:
        return False

def managed_airports(user=None):
    user_profile = Auth().lookup_user(user_data=user) if user else Auth().get_user()
    if can_query_user(user_profile):
        manages = AirportManager.objects.filter(user=user_profile.django_user(), status_code="A").select_related("airport")
        return [mgmt.airport for mgmt in manages if mgmt.is_active]
    return []

def managed_airport_identifiers(user=None):
    return [airport.identifier for airport in managed_airports(user)]


def set_airport_manager(airport, user=None):
    user_profile = Auth().lookup_user(user_data=user) if user else Auth().get_user()

    # If account is inactive, re-activate it
    try:
        if not user_profile.is_active:
            du = user_profile.django_user()
            du.is_active = True
            du.save()
    except Exception as ee:
        log.error(f"Could not activate user {user_profile}: {ee}")

    if not user_profile.is_valid():
        log.error(f"Invalid user may not be an airport manager: {user_profile}")
        return False

    # Look for existing management relation (may not be active)
    try:
        existing = AirportManager.objects.get(user=user_profile.django_user(), airport=airport)
    except AirportManager.DoesNotExist:
        existing = None

    try:
        if existing:
            existing.status_code = "A"
            existing.save()
            Auth.audit(
                "U", "MANAGEMENT",
                "Activated airport manager relationship",
                reference_code="AirportManager", reference_id=existing.id
            )
            return True
        else:
            new_manager = airport.management.create(user=user_profile.django_user(), airport=airport)
            Auth.audit(
                "C", "MANAGEMENT",
                "Created airport manager relationship",
                reference_code="AirportManager", reference_id=new_manager.id
            )
            return True
    except Exception as ee:
        log.error(f"Could not set airport manager: {ee}")
    return False


def deactivate_airport_manager(airport, user):
    log.trace([airport, user])
    try:
        user_profile = Auth().lookup_user(user_data=user)
        manager = AirportManager.objects.get(user=user_profile.django_user(), airport=airport)
        manager.status_code = "I"
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

def get_pending_invitations(airport, role=None):
    q = Invitation.objects.filter(airport=airport, status_code__in=["I", "S"]).select_related("invited_by")
    if role:
        q = q.filter(role=role)
    return q
