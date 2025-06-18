from django.db import models

import the_hangar_hub.models.hangar
from base.classes.util.log import Log
from django.utils import timezone
from zoneinfo import ZoneInfo

log = Log()


class Airport(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    display_name = models.CharField(max_length=200, blank=False, null=False)
    identifier = models.CharField(max_length=6, unique=True, db_index=True)
    city = models.CharField(max_length=60)
    state = models.CharField(max_length=3)
    country = models.CharField(max_length=3, null=True, blank=True)
    timezone = models.CharField(max_length=50, blank=True, null=True)

    # Email displayed to users/tenants who need to contact the airport
    info_email = models.CharField(max_length=150, blank=True, null=True)

    # A referral code is required to claim a new airport
    referral_code = models.CharField(max_length=30, blank=True, null=True, db_index=True)
    status_code = models.CharField(max_length=1, default="I")

    def is_active(self):
        return self.status_code != "I"  # ToDo: revisit when more statuses exist

    def activate_timezone(self):
        if self.timezone:
            timezone.activate(ZoneInfo(self.timezone))
        else:
            timezone.deactivate()

    def get_building(self, building_identifier):
        if str(building_identifier).isnumeric():
            return self.buildings.get(pk=building_identifier)
        else:
            return self.buildings.get(code=building_identifier)

    def get_hangar(self, hangar_identifier):
        try:
            if str(hangar_identifier).isnumeric():
                return the_hangar_hub.models.hangar.Hangar.objects.get(building__airport=self, pk=hangar_identifier)
            else:
                return the_hangar_hub.models.hangar.Hangar.objects.get(building__airport=self, code=hangar_identifier)
        except the_hangar_hub.models.hangar.Hangar.DoesNotExist:
            return None

    @classmethod
    def get(cls, id_or_ident):
        log.trace([id_or_ident])
        try:
            if str(id_or_ident).isnumeric():
                log.debug(f"Get by ID: {id_or_ident}")
                return cls.objects.get(pk=id_or_ident)
            else:
                return cls.objects.get(identifier=id_or_ident)
        except cls.DoesNotExist:
            log.debug(f"Airport not found: {id_or_ident}")
            return None
        except Exception as ee:
            log.error(f"Could not get airport: {ee}")
            return None
