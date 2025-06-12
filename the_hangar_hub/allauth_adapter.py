from allauth.account.models import EmailAddress
from allauth.account.utils import perform_login
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.core.exceptions import ObjectDoesNotExist
from the_hangar_hub import settings
from django.contrib.auth.models import User
from base.classes.util.env_helper import Log
from base.allauth_adapter import BaseSocialAdapter, BaseAccountAdapter
from the_hangar_hub.models.invitation import Invitation
from the_hangar_hub.services import airport_service
from base.services import message_service

log = Log()

class HubAccountAdapter(DefaultAccountAdapter):
    def login(self, request, user):
        # Standard login...
        BaseAccountAdapter().login(request, user)

        # Custom processing...
        log.debug("######## HUB LOGIN ....")

        # Look for invitations (manager, tenant, etc)
        # Must look for all confirmed emails
        confirmed_emails = list(EmailAddress.objects.filter(user=user, verified=True))
        confirmed_emails.append(user.email)
        for email in list(set(confirmed_emails)):
            for ii in Invitation.objects.filter(email__iexact=email, status_code__in=["I", "S"]):
                if ii.role == "MANAGER":
                    if airport_service.set_airport_manager(ii.airport, user):
                        message_service.post_success(f"bi-airplane You are now a manager for {ii.airport.display_name}!")
                        ii.resulting_user = user
                        ii.change_status("A")
                        ii.save()

    def clean_email(self, email: str) -> str:
        """
        Validates an email value. You can hook into this if you want to
        (dynamically) restrict what email addresses can be chosen.
        """
        return BaseAccountAdapter().clean_email(email)

    def send_mail(self, template_prefix: str, email: str, context: dict) -> None:
        BaseAccountAdapter().send_mail(template_prefix, email, context)


class HubSocialAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):

        """
        Invoked just after a user successfully authenticates via a
        social provider, but before the login is actually processed
        (and before the pre_social_login signal is emitted).

        sociallogin: <allauth.socialaccount.models.SocialLogin>
        """
        # Account logic from base app
        BaseSocialAdapter().pre_social_login(request, sociallogin)

        log.debug("Hub SocialAuth Adapter")




