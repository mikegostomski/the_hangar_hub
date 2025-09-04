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


def get_tenant_rentals(user=None, airport=None):
    user = Auth().lookup_user(user) if user else Auth.current_user()
    if user and user.id:
        if airport:
            return RentalAgreement.present_rental_agreements().filter(tenant__user=user, hangar__building__airport=airport)
        else:
            return RentalAgreement.present_rental_agreements().filter(tenant__user=user)
    return None


# def get_hangar_rental(airport_identifier, hangar_identifier, user=None, post_error=True):
#     user = Auth().lookup_user(user) if user else Auth.current_user()
#     airport = Airport.get(airport_identifier)
#     hangar = rental = None
#     if airport:
#         hangar = airport.get_hangar(hangar_identifier)
#     if post_error and not hangar:
#         message_service.post_error("The specified hangar could not be found")
#         return None
#
#     if hangar:
#         try:
#             rental = RentalAgreement.present_rental_agreements().get(hangar=hangar, tenant__user=user)
#             return rental
#         except RentalAgreement.DoesNotExist:
#             pass
#
#     message_service.post_error("The specified hangar rental could not be found")
#     return None
