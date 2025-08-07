from base.classes.util.env_helper import Log, EnvHelper
from base.services import utility_service
from base.models.utility.error import Error
from base.classes.auth.dynamic_role import DynamicRole
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User, AnonymousUser
from django.utils.functional import SimpleLazyObject
from base.models.contact.contact import Contact
from django.db.models import Q
from datetime import datetime, timezone
from allauth.account.models import EmailAddress

log = Log()
env = EnvHelper()


class UserProfile:

    # Properties matching the Django User model
    # ------------------------------------------------------
    @property
    def id(self):
        return self.user.id if self.user else None

    @property
    def first_name(self):
        return self.user.first_name if self.user else None

    @property
    def last_name(self):
        return self.user.last_name if self.user else None

    @property
    def username(self):
        return self.user.username if self.user else None

    @property
    def email(self):
        return self.user.email.lower() if self.user else None

    @property
    def is_staff(self):
        return self.user.is_staff if self.user else None

    @property
    def is_active(self):
        return self.user.is_active if self.user else None

    @property
    def is_superuser(self):
        return self.user.is_superuser if self.user else None

    @property
    def is_authenticated(self):
        return self.user.is_authenticated if self.user else None

    @property
    def is_anonymous(self):
        return self.user.is_anonymous if self.user else None
    # ------------------------------------------------------

    # Authentication/Authorization Data
    is_proxied = None
    authorities = None  # {"auth_code": "Auth Title", ...}

    # Holders for other classes (only do DB query once per request)
    user = None
    _cached_contact = None

    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def emails(self):
        return list(set([x.email.lower() for x in self.verified_email_records()] + [self.email]))

    def verified_email_records(self):
        return list(EmailAddress.objects.filter(user=self.user, verified=True))

    def allauth_email_records(self):
        return list(EmailAddress.objects.filter(user=self.user))

    def get_avatar_url(self):
        try:
            du = self.user
            if du:
                for account in SocialAccount.objects.filter(user=du):
                    if account.get_avatar_url():
                        return account.get_avatar_url()

        except Exception as ee:
            log.error("Could not get avatar URL: {ee}")
        return None

    def contact(self):
        self.get_contact_instance()
        return self._cached_contact

    def phone_number(self):
        return self.contact().phone_number()


    def has_authority(self, authority_list):
        """
        Does this user have the specified authority?
        If a list of authorities is given, only one of the authorities is required
        """
        try:
            # If user has no authorities, no need to process anything
            if not self.authorities:
                return False

            # If not already a list, make it so
            if type(authority_list) is not list:
                if ',' in authority_list:
                    authority_list = utility_service.csv_to_list(authority_list)
                else:
                    authority_list = [authority_list]

            # Expand out any dynamic roles
            master_list = []
            for authority_code in authority_list:
                if authority_code.startswith('~'):
                    master_list.extend(DynamicRole().get(authority_code))
                else:
                    master_list.append(authority_code)
            del authority_list

            # Look for any one matching authority
            for authority_code in master_list:
                if authority_code.lower() in self.authorities:
                    return True
        except Exception as ee:
            Error.record(ee, "Error checking user authorities")

        # False if not found
        return False

    def is_logged_in(self):
        # Do not count a proxied user as logged in
        if self.is_proxied:
            return False

        return self.is_authenticated

    def is_valid(self):
        return self.id and self.is_active

    def populate_supplemental_data(self, get_contact=True, get_authorities=True):
        if self.user and self.user.id:
            if get_authorities:
                self.populate_authorities()
            if get_contact:
                self.get_contact_instance()

    def __init__(self, user_data, get_contact=True, get_authorities=True):
        # If anonymous
        if user_data is None:
            self._make_anonymous()
            return

        # New from Django User
        elif type(user_data) in [User, SimpleLazyObject]:
            self.user = user_data

        # If already a UserProfile
        elif type(user_data) is UserProfile:
            pass

        # New from ID, username or email, or Stripe Customer ID
        else:
            try:
                if str(user_data).isnumeric():
                    self.user = User.objects.get(pk=user_data)
                elif '@' in user_data:
                    try:
                        self.user = User.objects.get(email__iexact=user_data)
                    except User.DoesNotExist:
                        # Look at other confirmed emails
                        confirmed_email = EmailAddress.objects.get(email__iexact=user_data, verified=True)
                        self.user = confirmed_email.user
                elif user_data.startswith("cus_") and "base_stripe" in env.get_setting("INSTALLED_APPS"):
                    from base_stripe.models.customer import Customer
                    sc = Customer.get(user_data)
                    if sc:
                        self.user = sc.user
                    else:
                        self.user = User.objects.get(username__iexact=user_data)
                else:
                    self.user = User.objects.get(username__iexact=user_data)
            except User.DoesNotExist:
                self._make_anonymous()
            except EmailAddress.DoesNotExist:
                self._make_anonymous()

        self.populate_supplemental_data(get_contact, get_authorities)

    def _make_anonymous(self):
        self.authorities = []
        self.user = AnonymousUser()
        self._cached_contact = None

    def populate_authorities(self, force=False):
        if force or self.authorities is None:
            self.authorities = {}
            if self.is_valid():

                # SuperUsers get the developer role
                if self.is_superuser:
                    self.authorities["developer"] = "Developer"

                try:
                    now = datetime.now(timezone.utc)
                    permissions = self.user.permissions.filter(Q(effective_date__isnull=True) | Q(effective_date__lte=now))
                    permissions = permissions.filter(Q(end_date__isnull=True) | Q(end_date__gt=now))
                    if permissions:
                        for pp in permissions:
                            self.authorities[pp.authority.code] = pp.authority.title
                except Exception as ee:
                    Error.record(ee, f"Error retrieving permissions for {self.email}")

    def get_contact_instance(self):
        if self._cached_contact:
            return

        # Contact is linked to User
        if not self.user:
            return

        # Get contact from User
        try:
            self._cached_contact = self.user.contact
        except:
            self._cached_contact = None

        # If no linked contact, search for existing one
        if not self._cached_contact:
            self._cached_contact = Contact.get(self.email)
            # If found, update user to match Contact
            if self._cached_contact:
                self.user.first_name = self._cached_contact.first_name
                self.user.last_name = self._cached_contact.last_name
                self.user.save()
                self._cached_contact.user = self.user
                self._cached_contact.save()
                # Refresh self with updated info
                self.populate_supplemental_data(get_contact=False, get_authorities=False)
                return
    
        # Create a new contact if needed
        if not self._cached_contact:
            # First and last are required, but may not exist in user object
            placeholder = self.user.username
            if not placeholder:
                placeholder = self.user.email.split('@')[0] if self.user.email else None
            self._cached_contact = Contact()
            self._cached_contact.user = self.user
            self._cached_contact.first_name = self.first_name or placeholder
            self._cached_contact.last_name = self.last_name or placeholder
            self._cached_contact.email = self.email
            self._cached_contact.save()
            return

    def __str__(self):
        if (self.first_name or self.last_name) and self.email:
            return f"{self.first_name} {self.last_name} <{self.email}>".strip()
        elif self.username and self.email:
            return f"{self.username} <{self.email}>"
        elif self.username:
            return self.username
        elif self.email:
            return self.email
        elif self.id:
            return str(f"<User: {self.id}>")
        else:
            return "Anonymous User"

    def __repr__(self):
        return str(self)
