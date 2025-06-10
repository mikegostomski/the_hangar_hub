from allauth.account.models import EmailAddress
from allauth.account.utils import perform_login
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.core.exceptions import ObjectDoesNotExist
from the_hangar_hub import settings
from django.contrib.auth.models import User
from base.classes.util.env_helper import Log

log = Log()

class BaseAccountAdapter(DefaultAccountAdapter):
    def login(self, request, user):
        # Standard login...
        DefaultAccountAdapter().login(request, user)

        # Custom processing...
        log.debug("######## LOGIN !!!!!!!!")

    def clean_email(self, email: str) -> str:
        """
        Validates an email value. You can hook into this if you want to
        (dynamically) restrict what email addresses can be chosen.
        """
        return email.lower() if email else email

class BaseSocialAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a user successfully authenticates via a
        social provider, but before the login is actually processed
        (and before the pre_social_login signal is emitted).

        sociallogin: <allauth.socialaccount.models.SocialLogin>

        We're trying to solve different use cases:
        - social account already exists, just go on
        - social account has no email or email is unknown, just go on
        - social account's email exists, link social account to existing user
        """
        log.debug("Base SocialAuth Adapter")


        # Ignore existing social accounts, just do this stuff for new ones
        if sociallogin.is_existing:
            return

        # some social logins don't have an email address, e.g. facebook accounts
        # with mobile numbers only, but allauth takes care of this case so just
        # ignore it
        if 'email' not in sociallogin.account.extra_data:
            return

        # check if given email address already exists.
        # Note: __iexact is used to ignore cases
        try:
            existing_user = None
            this_email = sociallogin.account.extra_data['email'].lower()

            # Check Django User objects
            try:
                existing_user = User.objects.get(email__iexact=this_email)
            except User.DoesNotExist:
                pass

            # Also check for verified emails added via allauth
            if not existing_user:
                try:
                    email_address = EmailAddress.objects.get(email__iexact=this_email, verified=True)
                    if email_address:
                        existing_user = email_address.user
                except EmailAddress.DoesNotExist:
                    pass

            # delete any non-verified instances of this email
            # An existing non-verified email will prevent a user from logging in via this email
            try:
                EmailAddress.objects.filter(email__iexact=this_email, verified=False).delete()
            except:
                return

            # if email not found, let allauth take care of this new social account
            if not existing_user:
                return
        except EmailAddress.DoesNotExist:
            return

        # if it does, connect this new social login to the existing user
        sociallogin.connect(request, existing_user)

