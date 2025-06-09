from allauth.account.signals import user_signed_up
from allauth.socialaccount.signals import pre_social_login
from django.dispatch import receiver
from django.contrib.auth.models import User
from base.classes.util.env_helper import Log, EnvHelper

log = Log()

log.debug("Loading signals...")

@receiver(user_signed_up, sender=User)
def user_signed_up(request, user, **kwargs):
    print("####################")
    log.trace()
    log.debug(locals())


@receiver(pre_social_login, sender=User)
def pre_social_login(request, sociallogin, **kwargs):
    print("####################")
    log.trace()
    log.debug(locals())
