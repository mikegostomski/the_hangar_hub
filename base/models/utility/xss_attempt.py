from django.db import models
from base.classes.util.log import Log
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from datetime import datetime
import pytz

log = Log()


class XssAttempt(models.Model):
    """Potential XSS attempts"""

    # Fields
    app_code = models.CharField(
        max_length=15,
        verbose_name="Application Code",
        help_text="Application that this attempt was made in.",
        blank=False,
        null=False,
    )

    # Associated user account
    user_username = models.CharField(max_length=30, blank=True, null=True)

    # Admin reviewer
    reviewer_username = models.CharField(max_length=30, blank=True, null=True)

    # Fields
    path = models.CharField(
        max_length=200,
        help_text='Request path',
        blank=False, null=False
    )
    parameter_name = models.CharField(
        max_length=80,
        help_text='Parameter name',
        default=None, blank=True, null=True
    )
    parameter_value = models.CharField(
        max_length=500,
        help_text='Parameter content',
        default=None, blank=True, null=True
    )
    session_key = models.CharField(
        max_length=100, help_text="Session Key", default=None, blank=True, null=True
    )
    date_created = models.DateTimeField(auto_now_add=True)

    def session_key_trunc(self):
        if self.session_key:
            return f"{self.session_key[:4]}...{self.session_key[-4:]}"
        return None

    def get_session(self):
        try:
            if self.session_key:
                return Session.objects.get(session_key=self.session_key)
        except:
            pass
        return None

    def session_status(self):
        ss = self.get_session()
        if ss and ss.expire_date > datetime.now(pytz.utc):
            return "A"

        elif ss:
            return "E"
        else:
            return "D"

    @classmethod
    def get(cls, xss_id):
        try:
            return XssAttempt.objects.get(pk=xss_id)
        except XssAttempt.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get XssAttempt: {ee}")
            return None
