from django.db import models
from base.classes.util.log import Log

log = Log()


class Authority(models.Model):
    """
    An authority is an action that can be granted to users
    """
    date_created = models.DateTimeField(auto_now_add=True)

    code = models.CharField(max_length=30, blank=False, null=False, unique=True, db_index=True)
    title = models.CharField(max_length=60, blank=False, null=False)
    description = models.CharField(max_length=80, blank=True, null=True)
