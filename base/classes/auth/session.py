"""
This is the definitive source of all authenticated user data
    - Authenticated User: Actual user authenticated via password or Google Auth
    - Impersonated User: Site will treat authenticated user as this person
    - Proxied User: Authenticated user can act on behalf of this user for specific actions
"""
from base.services import message_service
from base.classes.auth.user_profile import UserProfile
from base.classes.util.app_data import EnvHelper, Log, AppData
from base.models.utility.audit import Audit

log = Log()
env = EnvHelper()
app = AppData()

session_var = "auth_tracking_dict"


class Auth:
    authenticated_user = None   # Actual user that logged in
    impersonated_user = None    # Pretending to be this user (i.e. nonprod testing)
    proxied_user = None         # Performing an action on behalf of this user

    def is_logged_in(self):
        """
        Is a user authenticated?
        """
        return self.authenticated_user and self.authenticated_user.is_logged_in()

    def is_impersonating(self):
        """
        Is user pretending to be someone else?
        """
        return self.impersonated_user

    def is_proxying(self):
        """
        Is user acting on behalf of someone else?
        """
        return self.proxied_user

    def get_current_user_profile(self):
        """
        Get user_profile for the authenticated user, or the user they are impersonating
        """
        if self.is_impersonating():
            return self.impersonated_user
        else:
            return self.authenticated_user

    def can_impersonate(self):
        """
        Is this user allowed to impersonate others?
        """
        return self.authenticated_user.has_authority('~impersonate')

    def can_proxy(self):
        """
        Is this user allowed to proxy others?
        """
        return self.get_current_user_profile().has_authority('proxy')

    @classmethod
    def current_user_profile(cls):
        """
        Get UserProfile of current user
        Returns: UserProfile (which may be empty if user was not found)
        """
        return cls().get_current_user_profile()

    @classmethod
    def current_user(cls):
        """
        Get Django User object for current user
        Returns: User or None
        """
        return cls().get_current_user_profile().user

    @classmethod
    def lookup_user_profile(cls, user_data, get_contact=False, get_authorities=False):
        """
        Get a user_profile from an email, username, User.id, User, or UserProfile
        Returns: UserProfile (which may be empty if user was not found)
        """
        return cls._lookup_user_profile(user_data, get_contact, get_authorities)

    @classmethod
    def lookup_user(cls, user_data):
        """
        Same as above, but returns Django User rather than a UserProfile
        Returns: User or None
        """
        return cls.lookup_user_profile(user_data).user

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
        """
        Audit an important event
        Returns: Audit object (calling code likely never uses the returned value)
        """
        return cls._audit(
            crud_code, event_code, comments, reference_code, reference_id, previous_value, new_value
        )

    def __init__(self, resume=True):
        """
        Initializes the Auth object.
        User data is cached for the duration of request, so multiple calls will not result in repeated database lookups.
        """
        # Get Django.auth.User
        user_instance = env.request.user

        # If user is not authenticated, there is nothing to process
        if not user_instance.is_authenticated:
            self.authenticated_user = self.lookup_user_profile(None)
            self._clean_users()
            return

        # Look up authenticated user's profile (from Django's user object)
        self.authenticated_user = self.lookup_user_profile(user_instance, get_authorities=True, get_contact=True)
        self.impersonated_user = self.proxied_user = None

        # Check for impersonation/proxy data
        data = env.get_session_variable(session_var) or {}
        if data.get("impersonated_user") and self.can_impersonate():
            self.impersonated_user = self.lookup_user_profile(data.get("impersonated_user"), get_authorities=True, get_contact=True)
        if data.get("proxied_user") and self.can_proxy():
            self.proxied_user = self.lookup_user_profile(data.get("proxied_user"), get_authorities=True, get_contact=True)

        self._clean_users()
        self.save()

    # ==========================================================================
    # Shortcuts above reference the functions below (just for browsability)
    # ==========================================================================

    @classmethod
    def _lookup_user_profile(cls, user_data, get_contact=False, get_authorities=False):
        if user_data is None:
            return UserProfile(None)
        elif type(user_data) is UserProfile:
            return user_data

        lookup_key = str(user_data)
        user_map = env.recall() or {}
        found_user = user_map.get(lookup_key)

        if not found_user:
            # Perform lookup
            log.debug(f"Performing lookup for {lookup_key} ({type(user_data)})")  # ToDo: Remove this line
            user_instance = UserProfile(user_data=user_data, get_contact=get_contact, get_authorities=get_authorities)
            # Add user_instance to dict
            if user_instance and user_instance.id:
                user_map[lookup_key] = user_instance
                found_user = user_map.get(lookup_key)
                # Store updated dict for duration of request
                env.store(user_map)

            log.debug(f"Cached Users: {user_map.keys()}")

        # If getting contact or authorities, lookup could have been previously cached without that data.
        # Calling the functions to get that data will not re-query if the data is already present
        if found_user:
            if get_authorities:
                found_user.populate_authorities()
            if get_contact:
                found_user.get_contact_instance()

        # Return UserProfile object (or None)
        return found_user or UserProfile(None)

    @classmethod
    def _audit(
        cls,
        crud_code,
        event_code,
        comments=None,
        reference_code=None,
        reference_id=None,
        previous_value=None,
        new_value=None,
    ):
        log.trace(locals())
        try:
            auth = Auth()
            audit = Audit()
            audit.app_code = app.get_app_code()
            audit.user = auth.authenticated_user.user
            if auth.is_impersonating():
                audit.impersonated_user = auth.impersonated_user.user
            if auth.is_proxying():
                audit.proxied_user = auth.proxied_user.user
            audit.crud_code = crud_code
            audit.event_code = event_code
            audit.comments = str(comments) if comments is not None else None
            audit.reference_code = reference_code
            audit.reference_id = reference_id
            audit.previous_value = previous_value
            audit.new_value = new_value
            audit.save()
            return audit
        except Exception as ee:
            log.error(f"Could not audit: {ee}")
            return None

    # ==========================================================================
    # ==========================================================================
    # Code below should not be called by other apps (only from the base app)
    # ==========================================================================
    # ==========================================================================
    def save(self):
        self._clean_users()
        env.set_session_variable(session_var, self._to_dict())

    def set_impersonated_user(self, user_data):
        if self.can_impersonate():
            if self.is_impersonating():
                message_service.post_info(f"bi-person-dash No longer impersonating {self.impersonated_user.display_name}")
            self.reset_session()
            if user_data is None:
                return True
            iu = self.lookup_user_profile(user_data, get_authorities=True, get_contact=True)
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
        if self.get_current_user_profile().has_authority("~proxy"):

            if self.is_proxying():
                message_service.post_info(f"bi-person-dash No longer proxying {self.proxied_user.display_name}")

            if user_data is None:
                self.proxied_user = None
                self.save()
                return True

            pu = self.lookup_user_profile(user_data, get_authorities=True, get_contact=True)
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

    def _to_dict(self):
        return {
            'authenticated_user': self.authenticated_user.id if self.authenticated_user else None,
            'impersonated_user': self.impersonated_user.id if self.impersonated_user else None,
            'proxied_user': self.proxied_user.id if self.proxied_user else None,
        }

    def _clean_users(self):
        # Verify authenticated user is logged in and active
        if (not self.authenticated_user) or (not self.authenticated_user.is_valid()) or not self.authenticated_user.is_authenticated:
            self.authenticated_user = self.lookup_user_profile(None)
            self.impersonated_user = self.proxied_user = None

        if self.impersonated_user:
            if (not self.impersonated_user.is_valid()) or (not self.can_impersonate()):
                self.impersonated_user = None

        if self.proxied_user:
            if (not self.proxied_user.is_valid()) or (not self.can_proxy()):
                self.proxied_user = None

    @classmethod
    def get(cls):
        log.error("DEPRECATED: Auth.get()")
        return Auth()

    def __str__(self):
        if not self.is_logged_in():
            return "Anonymous"
        else:
            s = [self.authenticated_user.username]
            if self.is_impersonating():
                s.append(f"as {self.impersonated_user}")
            if self.is_proxying():
                s.append(f"proxying {self.proxied_user}")
            return " ".join(s)

    def __repr__(self):
        return str(self)
