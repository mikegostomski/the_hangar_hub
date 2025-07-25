from .services import auth_service
from .classes.breadcrumb import Breadcrumb
from django.conf import settings
from base.classes.util.app_data import Log, EnvHelper, AppData
from datetime import datetime, timezone

log = Log()
env = EnvHelper()
app = AppData()


def util(request):
    breadcrumbs = []
    for bc in Breadcrumb.get():
        breadcrumbs.append(Breadcrumb(bc))

    app_code = app.get_app_code()
    app_version = app.get_app_version()

    preferred_date_format = "m/d/Y"
    preferred_time_format = "h:i A"

    model = {
        'app_code': app_code,
        'app_version': app_version,
        'absolute_root_url': env.absolute_root_url,

        # The home URL (path) depends on the existence of URL Context
        'home_url': '/',
        'custom_plugins': env.installed_plugins,

        # Prod vs Nonprod
        'is_production': env.is_prod,
        'is_non_production': env.is_nonprod,
        'is_development': env.is_development,

        # Breadcrumbs (can be set in the view with utility_service functions)
        'breadcrumbs': breadcrumbs,

        # Forms (submission errors will put a "prefill" dict in flash scope to pre-populate the form)
        "prefill": env.get_flash_scope("prefill"),

        # Posted messages at top of page by default. Setting option allows moving them to the bottom
        'posted_message_position': getattr(settings, 'POSTED_MESSAGE_POSITION', 'TOP').upper(),

        "now": datetime.now(timezone.utc),
        "preferred_date_format": preferred_date_format,
        "preferred_time_format": preferred_time_format,
        "preferred_datetime_format": f"{preferred_date_format} {preferred_time_format}"
    }

    # Get admin links for any installed custom plugins, and the current app
    plugin_admin_links = []
    apps = env.installed_plugins
    apps.update({app_code.lower(): app_version})
    for plugin, version in apps.items():
        if plugin.lower().startswith("django"):
            continue
        setting_name = f"{plugin.upper().replace('-', '_')}_ADMIN_LINKS"
        try:
            this_link_list = getattr(settings, setting_name)
            plugin_admin_links.extend(this_link_list)
        except AttributeError as ee:
            try:
                exec(f"from {plugin} import _DEFAULTS as {plugin}_defaults")
                these_links = eval(f"{plugin}_defaults['{setting_name}']")
                if these_links:
                    plugin_admin_links.extend(these_links)
            except Exception as ee:
                pass

    model['plugin_admin_links'] = sorted(plugin_admin_links, key=lambda i: i['label'])
    return model


def auth(request):
    auth_instance = auth_service.get_auth_instance()
    return {
        'is_authenticated': auth_instance.is_logged_in(),
        'is_logged_in': auth_instance.is_logged_in(),
        'current_user': auth_instance.get_current_user_profile(),
        'authenticated_user': auth_instance.authenticated_user,
        'proxied_user': auth_instance.proxied_user,
        'can_impersonate': auth_instance.can_impersonate(),
        'is_impersonating': auth_instance.is_impersonating(),
        'can_proxy': auth_instance.get_current_user_profile().has_authority('~proxy'),
        'is_proxying': auth_instance.is_proxying(),
        'is_developer': auth_service.has_authority("developer"),
        'is_admin': auth_service.has_authority("admin"),
        'avatar_url': auth_instance.get_current_user_profile().get_avatar_url(),
    }
