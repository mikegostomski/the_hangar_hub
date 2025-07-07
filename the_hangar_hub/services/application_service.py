import the_hangar_hub.models.hangar
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models import Hangar
from the_hangar_hub.models.tenant import Tenant, Rental
from the_hangar_hub.models.application import HangarApplication
from the_hangar_hub.models.airport_manager import AirportManager
from base.services import message_service
from the_hangar_hub.models.airport import Airport


log = Log()
env = EnvHelper()


def get_applications(user=None):
    use_recall = user is None
    if use_recall:
        result = env.recall()
        if result is not None:
            return result
    user = Auth().lookup_user(user) if user else Auth.current_user()
    if user and user.id:
        apps = HangarApplication.objects.filter(user=user).order_by("-last_updated")
        if use_recall:
            env.store(apps)
        return apps
    return []


def get_active_applications(user=None, airport=None):
    return [app for app in get_applications(user) if app.is_active and (airport is None or app.airport == airport)]


def get_incomplete_applications(user=None):
    log.debug(f"USER APPS: { [app for app in get_active_applications(user) if app.is_incomplete]}")
    return [app for app in get_active_applications(user) if app.is_incomplete]


def get_selected_application():
    """
    If an application has been selected by the manager for hangar assignment, get that application
    """
    selected_application_id = env.get_session_variable("selected_application")
    return HangarApplication.get(selected_application_id) if selected_application_id else None

def clear_selected_application():
    """
    If an application has been selected by the manager for hangar assignment, forget that application
    """
    env.set_session_variable("selected_application", None)
