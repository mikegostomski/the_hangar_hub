import the_hangar_hub.models.infrastructure_models
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models import Hangar
from the_hangar_hub.models.rental_models import Tenant, RentalAgreement
from the_hangar_hub.models.application import HangarApplication
from the_hangar_hub.models.airport_manager import AirportManager
from base.services import message_service
from the_hangar_hub.models.airport import Airport


log = Log()
env = EnvHelper()


def get_waitlist(airport):
    waitlist = list(airport.applications.filter(status_code=["L"]))
    if waitlist:
        waitlist.sort(key=lambda x: x.wl_sort_string)
    return waitlist
