import the_hangar_hub.models.hangar
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.auth import Auth
from the_hangar_hub.models import Hangar
from the_hangar_hub.models.tenant import Tenant, Rental
from the_hangar_hub.models.airport_manager import AirportManager
from the_hangar_hub.models.invitation import Invitation
from base.services import message_service
from the_hangar_hub.models.airport import Airport


log = Log()
env = EnvHelper()

def get_tenant_rentals(user=None):
    user_profile = Auth().lookup_user(user) if user else Auth().get_user()
    return Rental.current_rentals().filter(tenant__user=user_profile.user)


def get_hangar_rental(airport_identifier, hangar_identifier, user=None, post_error=True):
    user_profile = Auth().lookup_user(user) if user else Auth().get_user()
    airport = Airport.get(airport_identifier)
    hangar = rental = None
    if airport:
        hangar = airport.get_hangar(hangar_identifier)
    if post_error and not hangar:
        message_service.post_error("The specified hangar could not be found")
        return None

    if hangar:
        try:
            rental = Rental.current_rentals().get(hangar=hangar, tenant__user=user_profile.user)
            return rental
        except Rental.DoesNotExist:
            pass

    message_service.post_error("The specified hangar rental could not be found")
    return None
