from django.db import models
from base.classes.util.app_data import Log, AppData
from django.contrib.auth.models import User

log = Log()
app = AppData()


class Audit(models.Model):
    """Record of important things that happened"""

    # Fields
    app_code = models.CharField(
        max_length=15,
        verbose_name="Application Code",
        help_text="Application that this action was taken in.",
        blank=False,
        null=False,
    )

    # Associated user account
    user = models.ForeignKey(User, models.SET_NULL, related_name="actors", blank=True, null=True)
    impersonated_user = models.ForeignKey(User, models.SET_NULL, related_name="impersonated", blank=True, null=True)
    proxied_user = models.ForeignKey(User, models.SET_NULL, related_name="proxied", blank=True, null=True)

    # Type of action taken
    crud_code = models.CharField(
        # Create, Read, Update, Delete
        max_length=1,
        blank=False,
        null=False,
        db_index=True,
    )

    event_code = models.CharField(
        max_length=80,
        help_text="This string should identify the type of event",
        blank=False,
        null=False,
        db_index=True,
    )

    # Associated object (if applicable)
    reference_code = models.CharField(
        max_length=60, default=None, blank=True, null=True, db_index=True
    )
    reference_id = models.IntegerField(
        default=None, blank=True, null=True, db_index=True
    )
    previous_value = models.CharField(
        max_length=500,
        help_text="Value before change was made",
        default=None,
        blank=True,
        null=True,
    )
    new_value = models.CharField(
        max_length=500,
        help_text="Value after change was made",
        default=None,
        blank=True,
        null=True,
    )

    comments = models.TextField(
        help_text="Comments about the event",
        default=None,
        blank=True,
        null=True,
    )

    date_created = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get(cls, id):
        try:
            return cls.objects.get(pk=id)
        except cls.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get Audit: {ee}")
            return None

    @classmethod
    def post(
        cls,
        auth,
        crud_code,
        event_code,
        comments=None,
        reference_code=None,
        reference_id=None,
        previous_value=None,
        new_value=None,
    ):
        audit = Audit()
        audit.app_code = app.get_app_code()
        audit.user = auth.authenticated_user.user
        audit.impersonated_user = auth.impersonated_user.user
        audit.proxied_user = auth.proxied_user.user
        audit.crud_code = crud_code
        audit.event_code = event_code
        audit.comments = str(comments) if comments is not None else None
        audit.reference_code = reference_code
        audit.reference_id = reference_id
        audit.previous_value = previous_value
        audit.new_value = new_value
        audit.save()
        return audit
