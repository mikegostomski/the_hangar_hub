from django.urls import path
from . import views

urlpatterns = [
    # A simple test page
    path("", views.infotext_index, name="index"),
    path("update", views.infotext_update, name="update"),
    path("delete", views.infotext_delete, name="delete"),
    path("group", views.infotext_update_group, name="group"),
]
