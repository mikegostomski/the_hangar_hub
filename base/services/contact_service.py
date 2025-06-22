from base.classes.util.log import Log
from base.models import Contact
from base.classes.auth.session import Auth
from base.models.contact.phone import Phone

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
