from django.conf import settings
from crequest.middleware import CrequestMiddleware
from inspect import getframeinfo, stack, getmembers
from base.classes.util.log import Log
import os
import sys

log = Log()
unit_test_session = {'modified': False, 'warned': False}
session_prefix = 'bcsv~'  # Base Custom Session Variable

class EnvHelper:

    #
    # REQUEST INFO
    # ##########################################################################

    @property
    def parameters(self):
        """Get parameters as dict. This is mostly for logging parameters."""
        request = self.request
        if request:
            pp = request.GET.items() if request.method == "GET" else request.POST.items()
            return {kk: vv for kk, vv in pp if kk != "csrfmiddlewaretoken"}
        return {}

    @property
    def is_ajax(self):
        # request.is_ajax was deprecated in Django 3.1 and no longer exists in 3.2.10
        request = self.request
        return bool(request and request.headers.get('x-requested-with') == 'XMLHttpRequest')

    @property
    def browser(self):
        try:
            browser = self.request.META["HTTP_USER_AGENT"]
        except:
            browser = "Unknown"
        return browser

    @property
    def is_health_check(self):
        return 'HealthChecker' in self.browser


    #
    # ENVIRONMENT INFO
    # ##########################################################################

    @property
    def is_prod(self):
        return self.environment_code == "PROD"

    @property
    def is_nonprod(self):
        return self.environment_code != "PROD"

    @property
    def is_development(self):
        return self.environment_code == "DEV"

    @property
    def static_content_url(self):
        if self.is_prod:
            return 'https://sunny-kulfi-ca2031.netlify.app/cdn'
            # return 'https://d3hj6oqj41ttxz.cloudfront.net'
        else:
            # ToDo: Stage CDN
            return 'https://sunny-kulfi-ca2031.netlify.app/cdn'


    #
    # CUSTOM SESSION VARIABLES (duration: session)
    # ##########################################################################

    def set_session_variable(self, var_name, value):
        # Prefix all custom session entries
        var = f"{session_prefix}{var_name}"
        self.session[var] = value
        return value

    def get_session_variable(self, var_name, alt=None):
        # Prefix all custom session entries
        var = f"{session_prefix}{var_name}"
        return self.session.get(var, alt)

    def clear_session_variables(self, preserve=None):
        """
        Clear all custom session variables
          preserve: a list of var_names to keep
        """
        request = self.request
        if preserve and type(preserve) is not list:
            preserve = [preserve]
        keep = [f"{session_prefix}{kk}" for kk in preserve] if preserve else None

        for kk in list(request.session.keys()):
            # Only delete custom variables (ignore Django values)
            if kk.startswith(session_prefix):
                if keep and kk in keep:
                    continue
                else:
                    del request.session[kk]
        request.session.modified = True


    #
    # PAGE SCOPE VARIABLES (duration: this request)
    # ##########################################################################

    def set_page_scope(self, var, val):
        var_name = f"page_scope_{var}"
        self.set_session_variable(var_name, val)
        return val

    def get_page_scope(self, var, alt=None):
        var_name = f"page_scope_{var}"
        return self.get_session_variable(var_name, alt)

    def clear_page_scope(self):
        session = self.session
        temp_vars = []
        for kk in session.keys():
            if kk.startswith(f'{session_prefix}page_scope_'):
                temp_vars.append(kk)
        # Remove the keys from the session
        for kk in temp_vars:
            del session[kk]

        session['modified'] = True


    #
    # FLASH SCOPE VARIABLES (duration: into the next request)
    # ##########################################################################

    def set_flash_scope(self, var, val):
        var_name = f"flash_scope_{var}"
        self.set_session_variable(var_name, val)
        return val

    def get_flash_scope(self, var, alt=None):
        # Get the value saved in previous request
        prev_var_name = f"flashed_scope_{var}"
        previous_flash_value = self.get_session_variable(prev_var_name, alt)

        # Get new value if overwritten during the current request
        new_var_name = f"flash_scope_{var}"
        new_flash_value = self.get_session_variable(new_var_name, 'flash-variable-not-set')

        # return the more recent of the two
        # (flash variable from last request can be overwritten this request)
        if new_flash_value != 'flash-variable-not-set':
            return new_flash_value
        else:
            return previous_flash_value

    def cycle_flash_scope(self):
        session = self.session
        flash_vars = []
        flashed_vars = []
        for kk in session.keys():
            if kk.startswith(f'{session_prefix}flash_scope_'):
                flash_vars.append(kk)
            elif kk.startswith(f'{session_prefix}flashed_scope_'):
                flashed_vars.append(kk)
        # Remove the keys from the flashed scope
        for kk in flashed_vars:
            del session[kk]
        # Move flash vars to flashed scope
        for kk in flash_vars:
            new_kk = kk.replace('flash_scope_', 'flashed_scope_')
            session[new_kk] = session[kk]
            del session[kk]

        session['modified'] = True


    #
    # STORE/RECALL
    # ##########################################################################

    def store(self, value, ignore_levels=0):
        """
        Store the result of a function for the duration of the request.
        Note: If the stored response is mutable, changes made to the returned value will affect the cached instance as well
        """
        self.set_page_scope(self._get_cache_key(ignore_levels), value)
        return value

    def recall(self, alt=None, ignore_levels=0):
        """
        Retrieve a stored result from a function run earlier in the request
        Note: If the stored response is mutable, changes made to the returned value will affect the cached instance as well
        """
        value = self.get_page_scope(self._get_cache_key(ignore_levels))
        if value is None:
            return alt
        return value

    #
    # REMEMBER/RETRIEVE
    # (same as store/recall, but for the session duration rather than request)
    # ##########################################################################

    def remember(self, value, ignore_levels=0):
        """
        Store the result of a function for the duration of the session.
        Note: If the stored response is mutable, changes made to the returned value will affect the cached instance as well
        """
        self.set_session_variable(self._get_cache_key(ignore_levels), value)
        return value

    def retrieve(self, alt=None, ignore_levels=0):
        """
        Retrieve a stored result from a function run earlier in the session
        Note: If the stored response is mutable, changes made to the returned value will affect the cached instance as well
        """
        value = self.set_session_variable(self._get_cache_key(ignore_levels))
        if value is None:
            return alt
        return value

    @staticmethod
    def _get_cache_key(ignore_levels=0):
        """
        Private function
        Get the key used by store/recall functions above
        UPDATE: This is also used for remembering pagination sort/order
        """
        # Ignore this function, and the store/recall function that called it (and any additional specified)
        depth = 2 + ignore_levels

        # Get the info about the function that called the store/recall function
        caller = getframeinfo(stack()[depth][0])

        # Use filename without .py extension
        filename = os.path.basename(caller.filename)[:-3]

        return f"cache-{filename}-{caller.function}"

    def test_cache_key(self):
        """
        The only purpose of this function is to unit test the "cache key" generated above
        """
        return self._get_cache_key()

    def test_store_recall(self, value=None):
        """
        The only purpose of this function is to unit test the store/recall feature
        """
        if value:
            self.store(value)
        else:
            return self.recall()


    #
    #
    # ##########################################################################

    @property
    def nonprod_email_addresses(self):
        """
        When sending mail from non-production, only these addresses are allowed to receive emails.
        Emails with no allowed recipients will be redirected to the logged-in user's email address
        """
        emails = self.get_setting("NONPROD_EMAIL_ALLOWED_RECIPIENTS") or []
        if type(emails) is not list:
            log.error("Invalid value for NONPROD_EMAIL_ALLOWED_RECIPIENTS. Should be a list of email addresses.")
            emails = []
        emails.append(self.nonprod_default_recipient)
        return list(set([x.lower() for x in emails if x]))

    @property
    def nonprod_default_recipient(self):
        """
        In non-production, send email to this address when no allowed address is present
        """
        if self.is_prod:
            return None

        # When authenticated, default to authenticated user
        if not self.is_development:
            # Not for local development, where I'm authenticating with fake addresses
            request = self.request
            user = request.user
            if user.is_authenticated and user.email:
                return user.email.lower()

        # When not authenticated, allow a default address to be specified and stored in the session
        session_default = self.get_session_variable("base_default_recipient")
        # Last resort is the default recipient defined in settings.py
        global_default = self.get_setting("NONPROD_EMAIL_DEFAULT_RECIPIENT")
        return session_default or global_default or "mikegostomski@gmail.com"


    @property
    def installed_plugins(self):
        """
        Get a dict of the installed custom plugins and their versions
        """
        installed_apps = {}
        for app_name in self.get_setting("INSTALLED_APPS"):
            if app_name.startswith("mjg"):
                version = "?.?.?"
                try:
                    for stuff in getmembers(sys.modules[f"{app_name}"]):
                        if "__version__" in stuff:
                            version = stuff[1]
                except Exception as ee:
                    log.debug(f"Cannot determine version of {app_name}")
                installed_apps[app_name] = version

        return installed_apps


    #
    # PROPERTIES
    # ##########################################################################

    @property
    def environment_code(self):
        """ DEV, STAGE, PROD """
        env = settings.ENVIRONMENT.upper()
        if env in ["DEV", "STAGE", "PROD"]:
            return env
        else:
            return 'DEV'

    @property
    def request(self):
        return CrequestMiddleware.get_request()

    @property
    def session(self):
        # While unit testing, there will be no request
        request = self.request

        if request is None:
            # This should not happen in prod, but just to be sure
            if self.is_prod:
                log.error("Request does not exist. Could not retrieve session.")
                return None
            else:
                # Only warn about this once (to prevent cluttered logs)
                if not unit_test_session.get('warned'):
                    log.warning("No request. Using dict as session (assumed unit testing)")
                    unit_test_session['warned'] = True
                return unit_test_session
        else:
            return request.session

    @classmethod
    def get_setting(cls, property_name, default_value=None):
        """
        * Get the value of a setting from settings.py (including local_settings.py)
        * For AWS instances, environment variables will be prioritized. This allows
          settings to be overridden without a redeployment.
        * Note: In some cases, using a Variable might make more sense, as they can
          be updated via a web interface in the admin menu (gear icon)
        """
        if settings.IS_DEPLOYED:
            # Look in environment variable first
            env_property = os.environ.get(property_name)
            if env_property is not None:
                # Allow clearing a previously-set value by setting it to "None"
                if str(env_property).upper() == "NONE":
                    pass  # Use value from settings.py (or default_value if not found)
                # Convert True/False strings to boolean values
                elif str(env_property).upper() in ["TRUE", "FALSE"]:
                    return str(env_property).upper() == "TRUE"
                # Convert numbers
                elif str(env_property).isnumeric():
                    return int(env_property)
                # Use string as-is
                else:
                    return env_property

        # If setting is defined in settings.py or local_settings.py
        if hasattr(settings, property_name):
            return getattr(settings, property_name)
        else:
            return default_value

    def __init__(self):
        pass