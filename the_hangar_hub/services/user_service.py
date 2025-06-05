from base.classes.util.env_helper import Log, EnvHelper
from base.services import auth_service
from the_hangar_hub.models.airport_manager import AirportManager

log = Log()
env = EnvHelper()

def is_airport_manager(user=None, airport=None):
    if not user:
        pass
