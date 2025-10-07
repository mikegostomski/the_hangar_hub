from django.db import models
from base.classes.util.env_helper import EnvHelper, Log

log = Log()
env = EnvHelper()


class WebhookEvent(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    event_type = models.CharField(max_length=60)
    event_id = models.CharField(max_length=60)

    object_type = models.CharField(max_length=60, db_index=True)
    object_id = models.CharField(max_length=60, db_index=True)

    refreshed = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)

    @classmethod
    def get(cls, xx):
        try:
            return cls.objects.get(pk=xx)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None