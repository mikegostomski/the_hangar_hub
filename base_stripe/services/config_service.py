from base.models.utility.error import EnvHelper, Log, Error
import stripe
from decimal import Decimal
from django.urls import reverse
from base.services import message_service

log = Log()
env = EnvHelper()

def set_stripe_api_key():
    stripe.api_key = env.get_setting("STRIPE_KEY")
