from django.apps import AppConfig
from django.conf import settings

# Default settings
_DEFAULTS = {
    'AUTHORIZE_GLOBAL': False,      # Allow authorizing for other apps?

    # Admin Menu Items
    'BASE_ADMIN_LINKS': [
        {'url': "base:status", 'label': "Status Page", 'icon': "bi-heart-pulse"},
        {'url': "base:manage_authorities", 'label': "Authorities", 'icon': "bi-shield-lock", 'authorities': "~security_admin"},
        {'url': "base:manage_users", 'label': "User Accounts", 'icon': "bi-person-gear", 'authorities': "~security_admin"},
        {'url': "base:contact_list", 'label': "Contacts", 'icon': "bi-person-rolodex", 'authorities': "~contact_admin"},
        # {'url': "base:errors", 'label': "Error Log", 'icon': "bi-exclamation-triangle", 'authorities': "DynamicSuperUser"},
        # {'url': "base:emails", 'label': "Email Log", 'icon': "bi-envelope"},
        {'url': "base:features", 'label': "Feature Toggles", 'icon': "bi-toggle-on", 'authorities': "~superuser"},
        # {'url': "base:audit", 'label': "Audit Events", 'icon': "bi-calendar3-week-fill", 'authorities': "DynamicSecurityOfficer"},
        # {'url': "base:audit_xss", 'label': "XSS Attempts", 'icon': "bi-incognito", 'authorities': "DynamicSecurityOfficer"},
        # {'url': "base:finti", 'label': "Finti Interface", 'icon': "bi-laptop", 'authorities': "developer", 'feature': "finti_console", 'nonprod_only': True},
        # {'url': "base:session", 'label': "Session Contents", 'icon': "bi-cpu", 'authorities': "developer"},
        # {'url': "base:email", 'label': "Send Test Email", 'icon': "bi-send", 'authorities': "developer"},
        {'url': "base:export_db", 'label': "Database Export", 'icon': "bi-database", 'authorities': "developer"},
    ]
}


class BaseConfig(AppConfig):
    name = 'base'
    verbose_name = "The Base Plugin"

    def ready(self):
        # Use base middleware
        request_middleware = 'crequest.middleware.CrequestMiddleware'
        base_middleware = 'base.middleware.base_middleware.BaseMiddleware'
        xss_middleware = 'base.middleware.security_middleware.xss_prevention'
        for mm in [request_middleware, base_middleware, xss_middleware]:
            if mm not in settings.MIDDLEWARE:
                settings.MIDDLEWARE.append(mm)

    # Assign default setting values
    for key, value in _DEFAULTS.items():
        try:
            getattr(settings, key)
        except AttributeError:
            setattr(settings, key, value)
        # Suppress errors from DJANGO_SETTINGS_MODULE not being set
        except:
            pass