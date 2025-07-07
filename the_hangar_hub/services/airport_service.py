import the_hangar_hub.models.hangar
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models.airport import Airport
from the_hangar_hub.models.airport_manager import AirportManager
from the_hangar_hub.models.tenant import Rental
from base.services import message_service
from base.models.utility.error import Error


log = Log()
env = EnvHelper()


def is_airport_manager(user=None, airport=None):
    use_recall = user is None and airport is None
    result = None
    if use_recall:
        result = env.recall()
        if result is not None:
            return result

    user = Auth().lookup_user(user_data=user) if user else Auth.current_user()
    if can_query_user(user):
        manages = AirportManager.objects.filter(user=user, status_code="A").select_related("user")
        if airport:
            manages = manages.filter(airport=airport)
        result = bool([mgmt for mgmt in manages if mgmt.is_active])
    else:
        result = False
    if use_recall:
        env.store(result)
    return result


def is_tenant(user=None, airport=None):
    return bool(get_airport_tenant_rentals(user, airport))


def get_airport_tenant_rentals(user=None, airport=None):
    use_recall = user is None and airport is None
    if use_recall:
        result = env.recall()
        if result is not None:
            return result

    user = Auth().lookup_user(user) if user else Auth.current_user()
    airport = env.request.airport if not airport else airport
    if not (user and airport):
        return None

    try:
        result = Rental.current_rentals().filter(tenant__user=user, airport=airport)
        if use_recall:
            env.store(result)
    except Exception as ee:
        result = None
        Error.unexpected(
            "Unable to retrieve current rental agreements", ee
        )

    return result









def save_airport_selection(airport):
    env.set_session_variable(
        "thh-selected-airport", airport.identifier if type(airport) is Airport else airport
    )

def get_airport_selection():
    return env.get_session_variable("thh-selected-airport")


def can_query_user(user):
    """
    Can only run queries with related User field when the specified User object has been saved
    (This check works for either user or user_profile)
    """
    return user and user.id

def get_managers(airport=None, status=None):
    managers = AirportManager.objects.filter(airport=airport)
    if status:
        managers = managers.filter(status_code=status)
    managers = managers.select_related("airport", "user")
    return managers


def get_managed_airport(airport_identifier, post_error=True):
    try:
        user = Auth.current_user()
        if can_query_user(user):
            if type(airport_identifier) is the_hangar_hub.models.airport.Airport:
                airport = airport_identifier
            elif type(airport_identifier) is the_hangar_hub.models.hangar.Building:
                airport = airport_identifier.airport
            elif type(airport_identifier) is the_hangar_hub.models.hangar.Hangar:
                airport = airport_identifier.building.airport
            else:
                airport = Airport.get(airport_identifier)
            if not airport:
                if post_error:
                    message_service.post_error("The specified airport could not be found")
            elif is_airport_manager(user, airport):
                return airport
            elif post_error:
                message_service.post_error("You are not authorized to manage the specified airport")
    except Exception as ee:
        log.error(f"Could not get managed airport: {ee}")
    return None

def get_managed_building(airport_identifier, building_identifier, post_error=True):
    building = None
    try:
        airport = get_managed_airport(airport_identifier, post_error)
        if airport:
            building = airport.get_building(building_identifier)
            if post_error and not building:
                message_service.post_error("The specified building could not be found")
    except Exception as ee:
        log.error(f"Could not get managed building: {ee}")
    return building

def get_managed_hangar(airport_identifier, hangar_identifier, post_error=True):
    hangar = None
    try:
        airport = get_managed_airport(airport_identifier, post_error)
        if airport:
            hangar = airport.get_hangar(hangar_identifier)
            if post_error and not hangar:
                message_service.post_error("The specified hangar could not be found")
    except Exception as ee:
        log.error(f"Could not get managed hangar: {ee}")
    return hangar


def managed_airports(user=None):
    use_recall = user is None
    if use_recall:
        mas = env.recall()
        if mas is not None:
            return mas

    manages = []
    user = Auth().lookup_user(user_data=user) if user else Auth.current_user()
    if can_query_user(user):
        manages = AirportManager.objects.filter(user=user, status_code="A").select_related("airport")
        manages = [mgmt.airport for mgmt in manages if mgmt.is_active]
    if use_recall:
        env.store(manages)
    return manages

def managed_airport_identifiers(user=None):
    return [airport.identifier for airport in managed_airports(user)]


def set_airport_manager(airport, user=None):
    user = Auth().lookup_user(user_data=user) if user else Auth.current_user()
    if (not user) or not getattr(user, "id"):
        return None

    # If the account is inactive, re-activate it
    try:
        if not user.is_active:
            user.is_active = True
            user.save()
    except Exception as ee:
        log.error(f"Could not activate user {user}: {ee}")

    if not user.is_active:
        log.error(f"Invalid user may not be an airport manager: {user}")
        return False

    # Look for existing management relation (may not be active)
    try:
        existing = AirportManager.objects.get(user=user, airport=airport)
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
            new_manager = airport.management.create(user=user, airport=airport)
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
        user_profile = Auth().lookup_user_profile(user_data=user)
        manager = AirportManager.objects.get(user=user_profile.user, airport=airport)
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

def get_pending_invitations(airport, role_code=None):
    q = the_hangar_hub.models.Invitation.objects.filter(airport=airport, status_code__in=["I", "S"]).select_related("invited_by")
    if role_code:
        q = q.filter(role_code=role_code)
    return q
