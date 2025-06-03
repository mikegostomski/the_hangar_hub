from django.db import models
from base.classes.util.log import Log
from django.contrib.auth.models import User
from base.models.auth.authority import Authority
from datetime import datetime
import pytz

log = Log()


class Permission(models.Model):
    """
    A permission joins a user to an authority
    """
    date_created = models.DateTimeField(auto_now_add=True)

    user = models.ForeignKey(User, models.CASCADE, related_name="permissions", blank=False, null=False, db_index=True)
    authority = models.ForeignKey(Authority, models.CASCADE, related_name="assignments", blank=False, null=False)

    effective_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)

    def since(self):
        return self.effective_date if self.effective_date else self.date_created

    def is_future(self):
        return self.effective_date and self.effective_date > datetime.now(pytz.utc)

    def is_history(self):
        return self.end_date and self.end_date <= datetime.now(pytz.utc)

    def is_active(self):
        return not (self.is_history() or self.is_future())

    def terminate(self):
        if self.is_future():
            self.delete()
        else:
            self.end_date = datetime.now(pytz.utc)
            self.save()
