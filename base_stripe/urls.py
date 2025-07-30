from django.urls import path
from . import views

urlpatterns = [
    # File previews via the upload_taglib will link to this endpoint:
    path("", views.home, name="home"),
    path("prices", views.show_prices, name="prices"),
    path("accounts", views.show_accounts, name="accounts"),
]
