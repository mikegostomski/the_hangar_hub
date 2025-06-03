from base.classes.util.log import Log
from base.models import Contact

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

