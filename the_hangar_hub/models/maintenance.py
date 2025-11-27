from django.db import models
from django.contrib.auth.models import User
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.session import Auth
from datetime import datetime, timezone
from django.db.models import Q

from the_hangar_hub.models import Hangar
from the_hangar_hub.services import airport_service

log = Log()
env = EnvHelper()


class MaintenanceRequest(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    date_resolved = models.DateTimeField(null=True, blank=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="maintenance_requests", db_index=True)
    tenant = models.ForeignKey("the_hangar_hub.Tenant", on_delete=models.CASCADE, related_name="maintenance_requests")
    hangar = models.ForeignKey('the_hangar_hub.Hangar', on_delete=models.CASCADE, related_name="maintenance_requests")
    airport = models.ForeignKey('the_hangar_hub.Airport', on_delete=models.CASCADE, related_name="maintenance_requests", db_index=True)

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

    def posted_by_them(self):
        return self.user.id != Auth.current_user().id

    def posted_by_me(self):
        return not self.posted_by_them()

    def posted_by_tenant(self):
        return self.user.id == Auth.current_user().id

    def posted_by_manager(self):
        log.trace([self])
        user = self.user
        airport = self.mx_request.airport
        key = f"mx-c-mgmt-{user}-{airport}"
        answer = env.get_session_variable(key)
        if True or answer is None:
            answer = airport_service.is_airport_manager(user, airport)
        return env.set_session_variable(key, answer)

    def can_view(self):
        # Public comment, or posted by me, or is manager
        return self.visibility_code == "P" or self.posted_by_me() or airport_service.manages_this_airport()

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