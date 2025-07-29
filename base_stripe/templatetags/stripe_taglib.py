from django import template
from django.utils.html import mark_safe
from base.classes.util.env_helper import Log, EnvHelper


register = template.Library()
log = Log()
env = EnvHelper()

