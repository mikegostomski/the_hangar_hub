from django.urls import path
from . import views

urlpatterns = [
    # File previews via the upload_taglib will link to this endpoint:
    path("", views.home, name="home"),
    path("webhook", views.webhook, name="webhook"),
    path("webhook/react", views.react_to_events, name="webhook_reaction"),
    path("sandbox/reset", views.reset_sandbox, name="reset_sandbox"),


    path("prices", views.show_prices, name="list_prices"),
    path("accounts", views.show_accounts, name="list_accounts"),
    path("accounts/modify", views.modify_account, name="modify_account"),
]
