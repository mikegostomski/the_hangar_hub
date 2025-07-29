from django.db import models
from django.contrib.auth.models import User
from base.classes.util.log import Log
from base.classes.auth.session import Auth
from datetime import datetime, timezone
from django.db.models import Q

from the_hangar_hub.models import Hangar

log = Log()


class MaintenanceRequest(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    date_resolved = models.DateTimeField(null=True, blank=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="maintenance_requests", null=True, blank=True, db_index=True) # ToDo: Not nullable
    tenant = models.ForeignKey("the_hangar_hub.Tenant", on_delete=models.CASCADE, related_name="maintenance_requests")
    hangar = models.ForeignKey('the_hangar_hub.Hangar', on_delete=models.CASCADE, related_name="maintenance_requests")

    summary = models.CharField(max_length=120)
    notes = models.TextField(null=True, blank=True)
    priority_code = models.CharField(max_length=1, default="S")
    status_code = models.CharField(max_length=1, default="S", db_index=True)

    @staticmethod
    def priority_options():
        return {
            "S": "Standard",
            "U": "Urgent",
            "H": "High",
            "M": "Medium",
            "L": "Low",
        }

    @property
    def priority(self):
        return self.priority_options().get(self.priority_code) or self.priority_code

    @staticmethod
    def status_options():
        return {
            "R": "Requested",
            "B": "Backlog",
            "T": "To Do List",
            "I": "In Progress",
            "S": "Stalled",
            "C": "Completed",
            "X": "Canceled",
            "D": "Declined",
        }

    @property
    def status(self):
        return self.status_options().get(self.status_code) or self.status_code

    def public_comments(self):
        return self.maintenance_comments.filter(visibility_code="P")

    def all_comments(self):
        return self.maintenance_comments.all()

    @classmethod
    def get(cls, data):
        try:
            return cls.objects.get(pk=data)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None


class MaintenanceComment(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="maintenance_comments")
    mx_request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name="maintenance_comments")

    comment = models.TextField()
    visibility_code = models.CharField(max_length=1, default="I")

    def is_them(self):
        return self.user.id != Auth.current_user().id

    def is_me(self):
        return not self.is_them()

    @staticmethod
    def visibility_options():
        return {
            "I": "Internal",
            "P": "Public",
        }

    @property
    def visibility(self):
        return self.visibility_options().get(self.visibility_code) or self.visibility_code

    @classmethod
    def get(cls, data):
        try:
            return cls.objects.get(pk=data)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None


class ScheduledMaintenance(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    status_code = models.CharField(max_length=1, default="S", db_index=True)
    date_resolved = models.DateTimeField(null=True, blank=True)

    tenant_request = models.ForeignKey(
        MaintenanceRequest, on_delete=models.CASCADE, related_name="scheduled_maintenance", null=True, blank=True, db_index=True
    )

    affected_hangar = models.ForeignKey(
        'the_hangar_hub.Hangar', on_delete=models.CASCADE, related_name="scheduled_maintenance", null=True, blank=True, db_index=True
    )
    affected_building = models.ForeignKey(
        'the_hangar_hub.Building', on_delete=models.CASCADE, related_name="scheduled_maintenance", null=True, blank=True, db_index=True
    )

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    summary = models.CharField(max_length=120)
    notes = models.TextField()

    @staticmethod
    def status_options():
        return {
            "S": "Scheduled",
            "C": "Completed",
            "H": "On Hold",
            "X": "Canceled",
        }

    def status(self):
        return self.status_options().get(self.status_code) or self.status_code

    @classmethod
    def get(cls, data):
        try:
            return cls.objects.get(pk=data)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get {cls}: {ee}")
            return None