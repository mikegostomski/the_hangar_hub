from django.db import models
from base.classes.util.app_data import Log, EnvHelper, AppData
from base.classes.auth.session import Auth
from base.models.utility.audit import Audit
from django.db.models import Q
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
import math
import os

log = Log()
app = AppData()
env = EnvHelper()


def get_upload_path(instance, filename):
    base_path = os.path.join(app.get_app_code().lower(), env.environment_code.lower())
    if instance.fs_path and instance.fs_path.startswith(base_path):
        upload_to = instance.fs_path
    else:
        upload_to = os.path.join(base_path, instance.fs_path)

    return upload_to


class UploadedFile(models.Model):
    """File Uploaded to S3 via base-upload"""

    # Fields
    app_code = models.CharField(
        max_length=15,
        verbose_name="Application Code",
        help_text="Application that this file belongs to.",
        db_index=True,
        blank=False,
        null=False,
    )
    owner = models.CharField(
        max_length=128,
        help_text="This holds username of the user that uploaded the file, which could be a provisional email address",
        blank=True,
        null=True,
    )
    content_type = models.CharField(max_length=128, blank=False, null=False)
    size = models.IntegerField(blank=False, null=False)
    date_created = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to=get_upload_path)

    # Although this can be obtained from the file object, having path and basename in the
    # database allows easier searching of the files via DB query
    fs_path = models.CharField(
        max_length=256,
        blank=False,
        null=False,
        help_text="Full S3 file path",
    )
    basename = models.CharField(
        max_length=128,
        blank=False,
        null=False,
        db_index=True,
        help_text="File name without the path info",
    )
    original_name = models.CharField(
        max_length=128,
        blank=False,
        null=False,
        help_text="Name of file as uploaded by user",
    )
    tag = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        help_text="Any sort of tag that will be useful for looking up files",
    )
    foreign_table = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        default=None,
        db_index=True,
        help_text="table or model that this file belongs to",
    )
    foreign_key = models.IntegerField(
        blank=True,
        null=True,
        default=None,
        db_index=True,
        help_text="ID of a record in another table that this file belongs to",
    )
    status = models.CharField(
        max_length=1,
        blank=True,
        null=True,
        db_index=True,
        help_text="Allow flags for Deleted, Archived, or maybe someday Scanned (for viruses)",
    )

    def readable_size(self):
        if self.size == 0:
            return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(self.size, 1024)))
        p = math.pow(1024, i)
        s = round(self.size / p, 1)
        return "%s %s" % (s, size_name[i])

    def is_image(self):
        return "image" in self.content_type

    def is_code(self):
        for x in ["html", "css", "javascript", "php", "csh", "java", "x-sh"]:
            if x in self.content_type:
                return True
        return False

    def icon_class(self):
        if self.is_image():
            return "bi bi-file-earmark-image"
        if "pdf" in self.content_type:
            return "bi bi-file-earmark-pdf"
        if "audio" in self.content_type:
            return "bi bi-file-earmark-music"
        if "video" in self.content_type:
            return "bi bi-file-earmark-play"
        if self.is_code():
            return "bi bi-file-earmark-code"
        if "zip" in self.content_type:
            return "bi bi-file-earmark-zip"
        if "word" in self.content_type:
            return "bi bi-file-earmark-word"
        if "excel" in self.content_type or "sheet" in self.content_type:
            return "bi bi-file-earmark-spreadsheet"
        if "powerpoint" in self.content_type or "presentation" in self.content_type:
            return "bi bi-file-earmark-slides"

        # This must come last to eliminate code files being identified as text
        if "text" in self.content_type and "calendar" not in self.content_type:
            return "bi bi-file-earmark-text"

        # All other types
        return "bi bi-file-earmark"

    def current_user_views(self):
        auth = Auth()
        cup = auth.get_current_user_profile()
        # When impersonating, look for views by the impersonated user, not just by sso user
        if auth.is_impersonating():
            return len(
                Audit.objects.filter(reference_code="UploadedFile", reference_id=self.id).filter(
                    Q(username=cup.username) | Q(impersonated_username=cup.username)
                )
            )
        else:
            return len(Audit.objects.filter(reference_code="UploadedFile", reference_id=self.id, username=cup.username))

    def total_views(self):
        """Does not include owner views"""
        return len(Audit.objects.filter(reference_code="UploadedFile", reference_id=self.id))


@receiver(post_delete, sender=UploadedFile)
def delete_file_on_record_delete(sender, instance, **kwargs):
    """
    Remove the file from storage when the UploadedFile is deleted.
    """
    file = getattr(instance, "file", None)
    if file and file.name:
        # This calls storage.delete under the hood; no extra save()
        file.delete(save=False)