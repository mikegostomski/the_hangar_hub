from django.db import models
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
    timezone = models.CharField(max_length=50, blank=True, null=True)

    # Email displayed to users/tenants who need to contact the airport
    info_email = models.CharField(max_length=150, blank=True, null=True)

    def activate_timezone(self):
        if self.timezone:
            timezone.activate(ZoneInfo(self.timezone))
        else:
            timezone.deactivate()


    @classmethod
    def get(cls, id_or_ident):
        try:
            if str(id_or_ident).isnumeric():
                log.debug(f"Get by ID: {id_or_ident}")
                return cls.objects.get(pk=id_or_ident)
            else:
                return cls.objects.get(identifier=id_or_ident)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get airport: {ee}")
            return None
