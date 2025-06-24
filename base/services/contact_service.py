from base.classes.util.log import Log
from base.models import Contact
from base.classes.auth.session import Auth
from base.models.contact.phone import Phone
from base.models.contact.address import Address

log = Log()


def create_contact_from_user(user_instance):
    # If user has no Contact info, create it now
    if user_instance:
        try:
            ct = user_instance.contact
            if ct:
                return ct
        except:
            ct = None

    # Look for existing contact with same email address
    ct = Contact.get(user_instance.email)
    if ct:
        user_instance.first_name = ct.first_name
        user_instance.last_name = ct.last_name
        user_instance.save()
        ct.user = user_instance
        ct.save()
        return ct

    # Create a new contact
    # First and last are required, but may not exist in user object
    placeholder = user_instance.username
    if not placeholder:
        placeholder = user_instance.email.split('@')[0]
    ct = Contact()
    ct.user = user_instance
    ct.first_name = user_instance.first_name if user_instance.first_name else placeholder
    ct.last_name = user_instance.last_name if user_instance.last_name else placeholder
    ct.email = user_instance.email
    ct.save()
    return ct

def add_phone_from_request(request, contact=None):
    if contact is None:
        user = Auth.current_user()
        contact = user.contact
    log.info(f"Adding phone for {contact}")

    pt = request.POST.get('phone_type')
    pp = request.POST.get('phone_prefix')
    pn = request.POST.get('phone_number')
    pe = request.POST.get('phone_ext')

    # Check for entry of area code into prefix
    if len(pp) == 3 and len(pn) == 7:
        pn = f"{pp}{pn}"
        pp = ''

    p = Phone()
    p.contact = contact
    if p.set_phone(pt, pp, pn, pe):
        # Check for duplicate
        try:
            existing = Phone.objects.get(
                contact=contact, phone_number=p.phone_number, extension=p.extension, prefix=p.prefix
            )
            del p
            return existing
        except Phone.DoesNotExist:
            p.save()
            return p
    else:
        return None


def add_address_from_request(request, contact=None):
    if contact is None:
        user = Auth.current_user()
        contact = user.contact
    log.info(f"Adding address for {contact}")

    if not (
            request.POST.get('street_1') or
            request.POST.get('city') or
            request.POST.get('state')
    ):
        log.info("No address was given")
        return None

    a = Address()
    a.contact = contact
    if a.set_all(
        request.POST.get('address_type'),
        request.POST.get('street_1'),
        request.POST.get('street_2'),
        request.POST.get('street_3'),
        request.POST.get('city'),
        request.POST.get('state'),
        request.POST.get('zip_code'),
        request.POST.get('country'),
    ):
        # Check for duplicate
        try:
            existing = Address.objects.get(
                contact=contact,
                street_1=a.street_1, street_2=a.street_2, street_3=a.street_3,
                city=a.city, state=a.state, zip_code=a.zip_code, country=a.country
            )
            del a
            return existing
        except Address.DoesNotExist:
            a.save()
            return a
    return None
