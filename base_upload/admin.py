from django.contrib import admin

# Register your models here.
from .models import UploadedFile
from .models import DatabaseFile

admin.site.register(UploadedFile)
admin.site.register(DatabaseFile)
