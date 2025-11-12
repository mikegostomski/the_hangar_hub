from base.classes.util.env_helper import Log, EnvHelper
from the_hangar_hub.models.rental_models import Tenant, RentalAgreement

log = Log()
env = EnvHelper()


def get_tenant(tenant_data):
    return Tenant.get(tenant_data)


def get_current_rental_agreements(tenant_data, airport=None):
    all_rental_agreements = get_rental_agreements(tenant_data, airport)
    return [x for x in all_rental_agreements if not x.is_present()] if all_rental_agreements else []


def get_relevant_rental_agreements(tenant_data, airport=None):
    all_rental_agreements = get_rental_agreements(tenant_data, airport)
    return [x for x in all_rental_agreements if not x.is_past()] if all_rental_agreements else []


def get_rental_agreements(tenant_data, airport=None):
    tenant = get_tenant(tenant_data)
    if tenant:
        key = f"{airport.identifier if airport else "none"}-{tenant.id}"
        answer = env.get_page_scope(key)
        if answer is None:
            if airport:
                return env.set_page_scope(
                    key,
                    RentalAgreement.relevant_rental_agreements().filter(tenant=tenant, airport=airport)
                )
            else:
                return env.set_page_scope(
                    key,
                    RentalAgreement.relevant_rental_agreements().filter(tenant=tenant)
                )
        return answer
    return None
