from django.db import models
from base.classes.util.log import Log
from base.services import utility_service, message_service, error_service
from base.models.contact.contact import Contact
from collections import OrderedDict
from base.services import validation_service

log = Log()


class Phone(models.Model):
    """
    Telephone numbers associated with a Contact
    """
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    # Associated user account
    contact = models.ForeignKey(
        Contact, models.CASCADE, related_name="phones", blank=False, null=False, db_index=True
    )

    ptype = models.CharField(max_length=1, blank=False, null=False)
    preferred = models.CharField(max_length=1, blank=False, null=False, default='N')

    phone_number = models.CharField(max_length=10, blank=False, null=False)
    extension = models.CharField(max_length=10, blank=True, null=True)
    prefix = models.CharField(max_length=5, blank=True, null=True)

    def set_ptype(self, ptype):
        if ptype in self.phone_types():
            self.ptype = ptype
            return True
        return False

    def set_prefix(self, prefix):
        self.prefix = validation_service.regex_replace(prefix, r'\D', '')
        return True

    def set_number(self, number):
        number = validation_service.regex_replace(number, r'\D', '')
        if len(number) == 10:
            self.phone_number = number
            return True
        return False

    def set_extension(self, extension):
        self.extension = validation_service.regex_replace(extension, r'\D', '')
        return True

    def set_phone(self, ptype, prefix, number, extension):
        log.trace([ptype, prefix, number, extension])
        valid = True
        if not self.set_ptype(ptype):
            message_service.post_error("Invalid telephone type")
            valid = False
        if not self.set_prefix(prefix):
            message_service.post_error("Invalid telephone prefix")
            valid = False
        if not self.set_number(number):
            message_service.post_error("Invalid telephone number. Please enter a 10-digit phone number.")
            valid = False
        if not self.set_extension(extension):
            message_service.post_error("Invalid telephone extension")
            valid = False
        return valid

    def make_primary(self):
        try:
            if self.preferred == 'N':
                for p in Phone.objects.filter(contact__id=self.contact.id, preferred='Y'):
                    p.preferred = 'N'
                    p.save()
                self.preferred = 'Y'
                self.save()
            return True
        except Exception as ee:
            error_service.unexpected_error("Unable to set preferred telephone number", ee)
            return False

    def formatted_number(self):
        pn = utility_service.format_phone(self.phone_number)
        if self.prefix and self.prefix != '1':
            pn = f"{self.prefix} - {pn}"
        if self.extension:
            pn = f"{pn} ext {self.extension}"
        return pn

    def phone_type(self):
        return self.phone_types().get(self.ptype)

    @classmethod
    def phone_types(cls):
        options = OrderedDict()
        options['C'] = 'Mobile'
        options['H'] = 'Home'
        options['W'] = 'Office'
        options['O'] = 'Other'
        return options

    @classmethod
    def get(cls, phone_id, contact=None):
        try:
            if contact:
                # Ensures phone belongs to contact
                return Phone.objects.get(pk=phone_id, contact__id=contact.id)
            else:
                return Phone.objects.get(pk=phone_id)
        except Phone.DoesNotExist:
            return None
        except Exception as ee:
            error_service.record(ee, [phone_id, contact])
