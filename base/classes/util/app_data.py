from django.conf import settings
from crequest.middleware import CrequestMiddleware
from inspect import getmembers
from base.classes.util.env_helper import EnvHelper, Log
import sys

log = Log()
env = EnvHelper()

class AppData:

    @staticmethod
    def get_primary_app_code():
        return env.get_setting("APP_CODE").upper()

    @staticmethod
    def sub_apps():
        # If the SUB_APPS dict is defined in settings.py, then there are sub-apps
        return env.get_setting("SUB_APPS")

    def get_app_options(self):
        apps = {self.get_app_code(): self.get_app_name()}
        subs = self.sub_apps()
        if subs:
            apps.update(subs)
        return apps

    def get_app_code(self):
        """
        Get the app code of the current application
        The app code is used to specify the current app in shared base tables
        The app code is also used for determining permissions
        """
        app_code = env.recall()
        if app_code:
            return app_code

        primary_app_code = app_in_use = self.get_primary_app_code()

        # Starting with v 3.0.0, an app can have multiple sub-apps
        if self.sub_apps():
            # Info about sub app usage is stored in session
            sub_app_info = self.get_sub_app_info(primary_app_code)
            last_app = sub_app_info["current_app"]

            # By convention, sub-app paths must start with the sub-app code
            request = env.request
            path = request.path if request else "/"
            pieces = [x for x in path.split("/") if x]
            # If there is URL context, sub-app code will be after the context
            sub_app_index = 1 if env.get_setting("URL_CONTEXT") else 0
            # Get potential sub-app code
            sub_app_code = (
                pieces[sub_app_index].upper() if len(pieces) > sub_app_index else None
            )

            # Is the potential sub-app code a defined sub-app?
            if sub_app_code and sub_app_code in self.sub_apps():
                app_in_use = sub_app_code

            # Is the potential sub-app code the primary app?
            elif sub_app_code and sub_app_code == primary_app_code:
                app_in_use = primary_app_code

            # Otherwise, use the last-known APP_CODE
            elif last_app:
                # Sub-app code persists into generic (base) pages until a new sub-app is visited
                app_in_use = last_app
            # If no previous app is known, use the primary APP_CODE
            else:
                app_in_use = primary_app_code

            # Update session app info
            app_changed = app_in_use != last_app
            if app_changed:
                log.trace(f"SUB-APP CHANGED from {last_app} to {app_in_use}")
            is_sub_app = app_in_use != primary_app_code
            sub_app_info = {
                "last_app": last_app,
                "current_app": app_in_use,
                "is_sub_app": is_sub_app,
                "app_changed": app_changed,
            }
            self.set_sub_app_info(sub_app_info)

        return env.store(app_in_use)

    def is_in_primary_app(self):
        if self.sub_apps():
            return self.get_app_code() == self.get_primary_app_code()
        else:
            return True

    @staticmethod
    def get_sub_app_info(primary_app_code=None):
        sub_app_info = {
            "last_app": primary_app_code,
            "current_app": None,
            "is_sub_app": None,
            "app_changed": False,
        }
        return env.get_session_variable("SUB_APP_INFO", sub_app_info)

    @staticmethod
    def set_sub_app_info(sub_app_info):
        env.set_session_variable("SUB_APP_INFO", sub_app_info)

    def get_app_name(self):
        """
        Get the human-readable name of the current application
        This is mainly used in administrative views
        """
        subs = self.sub_apps()
        if subs:
            app_code = self.get_app_code()
            if app_code in subs:
                return subs.get(app_code)
        return env.get_setting("APP_NAME")

    def get_app_version(self):
        """
        Get the version of the current application or sub-application
        """
        # Try to get from current app's (or sub-app's) __init__ version
        current_app_code = self.get_app_code().lower()
        try:
            for stuff in getmembers(sys.modules[current_app_code]):
                if "__version__" in stuff:
                    return stuff[1]
        except Exception as ee:
            log.debug(f"Cannot determine version of {current_app_code}")

        # Return version from settings if not found in __init__
        return env.get_setting("APP_VERSION")

    def __init__(self):
        pass