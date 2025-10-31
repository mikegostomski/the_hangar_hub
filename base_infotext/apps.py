from django.apps import AppConfig
from django.conf import settings
from base.classes.util.log import Log
log = Log()


# Default settings
_DEFAULTS = {
    # Admin Menu Items
    'PSU_INFOTEXT_ADMIN_LINKS': [
        {
            'url': "infotext:index", 'label': "Infotext", 'icon': "fa-pencil-square-o",
            'authorities': ["admin", "infotext", "developer"]
        },
    ]
}


class PsuInfotextConfig(AppConfig):
    name = 'base_infotext'

    def ready(self):
        # Assign default setting values
        log.debug("Setting default settings for base_infotext")
        for key, value in _DEFAULTS.items():
            try:
                getattr(settings, key)
            except AttributeError:
                setattr(settings, key, value)
            # Suppress errors from DJANGO_SETTINGS_MODULE not being set
            except ImportError as ee:
                log.debug(f"Error importing {key}: {ee}")
