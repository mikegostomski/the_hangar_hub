from django.db import models
from base.classes.util.log import Log
from django.contrib.auth.models import User
from base.services import message_service, validation_service

log = Log()


class Contact(models.Model):
    """
    Contact information (may be associated with a user account)
    """
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    # Associated user account
    user = models.OneToOneField(User, models.SET_NULL, related_name="contact", blank=True, null=True)

    # Identity info
    first_name = models.CharField(max_length=60, blank=False, null=False)
    last_name = models.CharField(max_length=60, blank=False, null=False, db_index=True)

    # Multiple emails may exist for associated User, but there's only one Contact email
    email = models.CharField(max_length=150, blank=False, null=False, db_index=True, unique=True)

    # Additional identity info
    gender = models.CharField(max_length=1, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    @property
    def display_name(self):
        try:
            # If account created without a name, email (pre-@) is inserted as f%l name
            email_as_names = self.first_name and self.first_name == self.last_name and self.first_name == self.email.split("@")[0]
        except:
            email_as_names = False

        if email_as_names:
            return self.first_name
        elif self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        elif self.user.first_name or self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}".strip()
        elif self.email:
            return self.email
        elif self.user.email:
            return self.user.email
        elif self.user:
            return str(self.user)
        else:
            "Empty Contact"

    def phone_number_options(self):
        return {str(x.id): x for x in self.phones.all()}

    def phone_number(self):
        phones = self.phones.all()
        if not phones:
            return None
        elif len(phones) == 1:
            return phones[0].formatted_number()
        pref_phones = [x for x in phones if x.is_primary()]
        if pref_phones:
            return pref_phones[0].formatted_number()
        else:
            return None

    def address_options(self):
        return {str(x.id): x for x in self.addresses.all()}

    def set_first_name(self, name):
        if name:
            self.first_name = name
            if self.user:
                self.user.first_name = name
                self.user.save()
            return True
        return False

    def set_last_name(self, name):
        if name:
            self.last_name = name
            if self.user:
                self.user.last_name = name
                self.user.save()
            return True
        return False

    def set_email(self, email):
        if email:
            email = email.lower().strip()
            if email == self.email:
                return True  # No change
            if not validation_service.is_email_address(email):
                message_service.post_error("The given email address appears to be invalid")
                return False
            other_contact = Contact.get(email)
            if other_contact:
                message_service.post_error("That email is already in use by another person")
                log.warning(f"{other_contact} has email: {email}")
                return False
            self.email = email
            # ToDo: Add email to list of user emails
            if self.user:
                self.user.email = email
                self.user.save()
            return True
        return False

    @classmethod
    def get(cls, id_or_email):
        try:
            if str(id_or_email).isnumeric():
                return Contact.objects.get(pk=id_or_email)
            else:
                # Email address should be unique
                return Contact.objects.get(email=id_or_email)
        except Contact.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get contact: {ee}")
            return None
