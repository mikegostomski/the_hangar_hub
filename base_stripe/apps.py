from django.apps import AppConfig
from django.conf import settings
from base.classes.util.log import Log

log = Log()


# Default settings
_DEFAULTS = {
    # Admin Menu Items
    "BASE_STRIPE_ADMIN_LINKS": [
        {
            'url': "stripe:webhook_reaction", 'label': "Process Webhooks", 'icon': "bi-stripe",
            'authorities': "developer"
        },
    ]
}


class BaseStripeConfig(AppConfig):
    name = "base_stripe"

    def ready(self):
        # Assign default setting values
        log.debug("Setting default settings for base_stripe")
        for key, value in _DEFAULTS.items():
            try:
                getattr(settings, key)
            except AttributeError:
                setattr(settings, key, value)
            # Suppress errors from DJANGO_SETTINGS_MODULE not being set
            except ImportError as ee:
                log.debug(f"Error importing {key}: {ee}")
