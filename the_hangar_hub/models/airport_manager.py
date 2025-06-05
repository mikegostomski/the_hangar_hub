from django.db import models
from base.classes.util.log import Log
from the_hangar_hub.models.airport import Airport
from django.contrib.auth.models import User

log = Log()


class AirportManager(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=1, blank=False, null=False, default="A")

    airport = models.ForeignKey(Airport, models.CASCADE, related_name="management", blank=False, null=False, db_index=True)
    user = models.ForeignKey(User, models.CASCADE, related_name="manages", blank=False, null=False, db_index=True)

    @classmethod
    def get(cls, rel_id):
        try:
            return cls.objects.get(pk=rel_id)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get airport-manager: {ee}")
            return None
