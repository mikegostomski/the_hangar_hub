from django.urls import path
from . import views

urlpatterns = [
    # File previews via the upload_taglib will link to this endpoint:
    path("file/<int:file_id>", views.linked_file, name="linked_file"),
]
