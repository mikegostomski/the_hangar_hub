from django.db import models
from base.classes.util.log import Log
from base.models.contact.contact import Contact
from collections import OrderedDict
from base.services import validation_service, message_service
from base.models.utility.error import Error

log = Log()


class Address(models.Model):
    """
    Addresses associated with a Contact
    """
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    # Associated user account
    contact = models.ForeignKey(
        Contact, models.CASCADE, related_name="addresses", blank=False, null=False, db_index=True
    )

    atype = models.CharField(max_length=1, blank=False, null=False)

    street_1 = models.CharField(max_length=80, blank=False, null=False)
    street_2 = models.CharField(max_length=80, blank=True, null=True)
    street_3 = models.CharField(max_length=80, blank=True, null=True)

    city = models.CharField(max_length=30, blank=False, null=False)
    state = models.CharField(max_length=2, blank=False, null=False)
    zip_code = models.CharField(max_length=15, blank=False, null=False)

    country = models.CharField(max_length=30, blank=True, null=True)

    def summary(self):
        streets = ", ".join([x for x in [self.street_1, self.street_2, self.street_3] if x])
        csz = f"{self.city}, {self.state} {self.zip_code}".strip()
        return f"{streets}, {csz}"

    def address_type(self):
        return self.address_types().get(self.atype)

    def set_atype(self, atype):
        if atype not in self.address_types():
            return False
        self.atype = atype
        return True

    def set_street(self, line, content):
        if content and len(content) > 80:
            log.error(f"Street {line} content too long: {len(content)}/80")
            return False
        # Allow pretty much anything in the street lines(?)
        if str(line) == '1':
            self.street_1 = content
        elif str(line) == '2':
            self.street_2 = content
        elif str(line) == '3':
            self.street_3 = content
        else:
            return False
        return True

    def set_city(self, city):
        if (not city) or validation_service.has_unlikely_characters(city):
            return False
        else:
            self.city = city[:30]
            return True

    def set_state(self, state):
        # ToDo: Get a list of valid states/provinces
        if (not state) or validation_service.has_unlikely_characters(state):
            return False
        else:
            self.state = state[:2]
            return True

    def set_zip_code(self, zip_code):
        if (not zip_code) or validation_service.has_unlikely_characters(zip_code):
            return False
        elif zip_code and len(zip_code) > 15:
            log.error(f"Zip code content too long: {len(zip_code)}/80")
            return False
        else:
            self.zip_code = zip_code
            return True

    def set_country(self, country):
        if country and validation_service.has_unlikely_characters(country):
            return False
        else:
            self.country = country[:30] if country else None
            return True

    def set_all(self, t, s1, s2, s3, c, s, z, n):
        valid = True
        if (not t) or not self.set_atype(t):
            message_service.post_error("Street line 1 is not valid")
            valid = False
        if (not s1) or not self.set_street(1, s1):
            message_service.post_error("Street line 1 is not valid")
            valid = False
        if not self.set_street(2, s2):
            message_service.post_error("Street line 2 is not valid")
            valid = False
        if not self.set_street(3, s3):
            message_service.post_error("Street line 3 is not valid")
            valid = False
        if not self.set_city(c):
            message_service.post_error("City is not valid")
            valid = False
        if not self.set_state(s):
            message_service.post_error("State is not valid")
            valid = False
        if not self.set_zip_code(z):
            message_service.post_error("Zip code is not valid")
            valid = False
        if not self.set_country(n):
            message_service.post_error("Country is not valid")
            valid = False
        return valid

    @classmethod
    def address_types(cls):
        options = OrderedDict()
        options['H'] = 'Home'
        options['S'] = 'Shipping'
        options['B'] = 'Billing'
        options['W'] = 'Office'
        options['O'] = 'Other'
        return options

    def address_type_icon(self):
        if self.atype == 'H':
            return 'bi bi-house'
        if self.atype == 'S':
            return 'bi bi-mailbox'
        if self.atype == 'B':
            return 'bi bi-cash-coin'
        if self.atype == 'W':
            return 'bi bi-building'

        return 'bi bi-inboxes'

    @classmethod
    def get(cls, address_id, contact=None):
        try:
            if contact:
                # Ensures phone belongs to contact
                return Address.objects.get(pk=address_id, contact__id=contact.id)
            else:
                return Address.objects.get(pk=address_id)
        except Address.DoesNotExist:
            return None
        except Exception as ee:
            Error.record(ee, [address_id, contact])

    def __str__(self):
        return self.summary()

    def __repr__(self):
        return str(self)
