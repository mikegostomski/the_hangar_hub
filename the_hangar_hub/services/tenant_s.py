import the_hangar_hub.models.infrastructure_models
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from the_hangar_hub.models import Hangar
from base.models.utility.error import Error
from the_hangar_hub.models.rental_models import Tenant, RentalAgreement
from the_hangar_hub.models.application import HangarApplication
from the_hangar_hub.models.airport_manager import AirportManager
from base.services import message_service
from the_hangar_hub.models.airport import Airport



log = Log()
env = EnvHelper()


def get_tenant(tenant_data):
    return Tenant.get(tenant_data)



def get_rental_agreements(tenant_data, airport=None):
    tenant = get_tenant(tenant_data)
    if tenant:
        if airport:
            return RentalAgreement.relevant_rental_agreements().filter(tenant=tenant, hangar__building__airport=airport)
        else:
            return RentalAgreement.relevant_rental_agreements().filter(tenant=tenant)
    return None
