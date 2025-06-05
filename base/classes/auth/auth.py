"""
This is the definitive source of all authenticated user data
    - Authenticated User: Actual user authenticated via password or Google Auth
    - Impersonated User: Site will treat authenticated user as this person
    - Proxied User: Authenticated user can act on behalf of this user for specific actions
"""
from base.services import message_service
from .auth_user import AuthUser
from base.classes.util.app_data import EnvHelper, Log, AppData
from base.models.utility.audit import Audit

log = Log()
env = EnvHelper()
app = AppData()

session_var = "auth_tracking_dict"


class Auth:
    authenticated_user = None
    impersonated_user = None
    proxied_user = None

    def is_logged_in(self):
        return self.authenticated_user and self.authenticated_user.is_logged_in()

    def is_impersonating(self):
        return self.impersonated_user

    def is_proxying(self):
        return self.proxied_user

    def get_user(self):
        if self.is_impersonating():
            return self.impersonated_user
        else:
            return self.authenticated_user

    def save(self):
        self._clean_users()
        env.set_session_variable(session_var, self._to_dict())

    def can_impersonate(self):
        return self.authenticated_user.has_authority('~impersonate')

    def set_impersonated_user(self, user_data):
        if self.can_impersonate():
            if self.is_impersonating():
                message_service.post_info(f"bi-person-dash No longer impersonating {self.impersonated_user.display_name}")
            self.reset_session()
            if user_data is None:
                return True
            iu = self.lookup_user(user_data, get_authorities=True, get_contact=True)
            if iu and iu.is_valid():
                self.impersonated_user = iu
                self.save()

                self.audit("R", "IMPERSONATE", f"Impersonating {self.impersonated_user.display_name}")

                message_service.post_info(f"bi-incognito Impersonating {self.impersonated_user.display_name}")
                return True
            else:
                message_service.post_error("Could not find the specified user to impersonate")
        return False

    def set_proxied_user(self, user_data):
        if self.get_user().has_authority("~proxy"):

            if self.is_proxying():
                message_service.post_info(f"bi-person-dash No longer proxying {self.proxied_user.display_name}")

            if user_data is None:
                self.proxied_user = None
                self.save()
                return True

            pu = self.lookup_user(user_data, get_authorities=True, get_contact=True)
            if pu and pu.is_valid():
                pu.is_proxied = True
                self.proxied_user = pu
                self.save()

                self.audit("R", "PROXY", f"Proxying {self.proxied_user.display_name}")

                message_service.post_info(f"bi-person-plus Proxying {self.proxied_user.display_name}")
                return True
            else:
                message_service.post_error("Could not find the specified user to proxy")
        return False

    def reset_session(self):
        env.clear_session_variables()
        self.impersonated_user = None
        self.proxied_user = None
        self.save()

    def __init__(self, resume=True):
        # Get Django.auth.User
        user_instance = env.request.user

        # If user is not authenticated, there is nothing to process
        if not user_instance.is_authenticated:
            self.authenticated_user = self.lookup_user(None)
            self._clean_users()
            return

        # Resume from session
        # ===============================================================
        if resume:
            self._resume()

            # Has user authentication changed?
            user_unchanged = self.authenticated_user and user_instance.username == self.authenticated_user.username

            # # If user did not change, check for name or email changes (stored in session)
            # for u_type in ['authenticated_user', 'impersonated_user', 'proxied_user']:
            #     user_class = getattr(self, u_type)
            #     if user_class:
            #         user_django = user_class.django_user()
            #         if user_django:
            #             save_changes = False
            #             for attr in ["first_name", "last_name", "email"]:
            #                 if getattr(user_django, attr) != getattr(user_class, attr):
            #                     setattr(user_class, attr, getattr(user_django, attr))
            #                     save_changes = True
            #             if save_changes:
            #                 self.save()

            # If authentication has not changed, no further processing required
            if user_unchanged:
                self._clean_users()
                return

        # Generate new auth data
        # ===============================================================
        self.authenticated_user = self.lookup_user(user_instance, get_authorities=True, get_contact=True)
        self.impersonated_user = None
        self.proxied_user = None
        self.save()

    def _resume(self):
        data = env.get_session_variable(session_var)
        if data:
            for au in ['authenticated_user', 'impersonated_user', 'proxied_user']:
                user_id = data.get(au)
                if user_id:
                    setattr(self, au, self.lookup_user(user_id, get_authorities=True, get_contact=True))

    def _to_dict(self):
        return {
            'authenticated_user': self.authenticated_user.id if self.authenticated_user else None,
            'impersonated_user': self.impersonated_user.id if self.impersonated_user else None,
            'proxied_user': self.proxied_user.id if self.proxied_user else None,
        }

    def _clean_users(self):
        if (not self.authenticated_user) or (not self.authenticated_user.is_valid()):
            self.authenticated_user = self.lookup_user(None)
        if self.impersonated_user and not self.impersonated_user.is_valid():
            self.impersonated_user = None
        if self.proxied_user and not self.proxied_user.is_valid():
            self.proxied_user = None

    @classmethod
    def get(cls):
        return Auth(resume=True)

    @classmethod
    def lookup_user(cls, user_data, get_contact=False, get_authorities=False):
        if user_data is None:
            return AuthUser(None)

        lookup_key = str(user_data)
        user_map = env.recall() or {}
        cached_user_instance = user_map.get(lookup_key)

        if not cached_user_instance:
            # Perform lookup
            log.trace([lookup_key])
            user_instance = AuthUser(user_data=user_data, get_contact=get_contact, get_authorities=get_authorities)
            # Add user_instance to dict
            if user_instance and user_instance.id:
                user_map[lookup_key] = user_instance
                # Store updated dict for duration of request
                env.store(user_map)
            log.debug(f"Cached Users: {user_map.keys()}")

        # Return AuthUser object (or None)
        return user_map.get(lookup_key)

    @classmethod
    def audit(
        cls,
        crud_code,
        event_code,
        comments=None,
        reference_code=None,
        reference_id=None,
        previous_value=None,
        new_value=None,
    ):
        auth = Auth.get()
        audit = Audit()
        audit.app_code = app.get_app_code()
        audit.user = auth.authenticated_user.django_user()
        if auth.is_impersonating():
            audit.impersonated_user = auth.impersonated_user.django_user()
        if auth.is_proxying():
            audit.proxied_user = auth.proxied_user.django_user()
        audit.crud_code = crud_code
        audit.event_code = event_code
        audit.comments = str(comments) if comments is not None else None
        audit.reference_code = reference_code
        audit.reference_id = reference_id
        audit.previous_value = previous_value
        audit.new_value = new_value
        audit.save()
        return audit