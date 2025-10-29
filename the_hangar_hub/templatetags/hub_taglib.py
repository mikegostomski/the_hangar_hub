#
#   All template tags provided by the Base plugin are registered in this file.
#   For browse-ability, all processing happens outside this file.
#

from django.conf import settings
from django import template
from base.models import Feature
from base.services import utility_service, auth_service, date_service, validation_service
from base.templatetags.tag_processing import html_generating, static_content
from django.urls import reverse
from decimal import Decimal
from django.utils.html import mark_safe
from django.template import TemplateSyntaxError
import time
from base.classes.util.app_data import Log, EnvHelper, AppData

log = Log()
env = EnvHelper()
app = AppData()

register = template.Library()


@register.inclusion_tag('the_hangar_hub/airport/_logo.html', takes_context=True)
def airport_logo(context, *args, **kwargs):
    airport = context.get("airport")
    return {"airport": airport, **kwargs}



@register.simple_tag(takes_context=True)
def change_airport_link(context, *args, **kwargs):
    # Where to go after selecting an airport
    if args and len(args) > 1:
        next_url = reverse(args[0], args=args[1:])
    elif args:
        next_url = reverse(args[0])
    else:
        next_url = None
    env.set_session_variable("thh-after-ap-selection-url", next_url)

    # Where to go to lookup airport
    url = "public:search"

    # An additional action may be needed (delete incomplete application)
    oc = kwargs.get("onclick")
    oc = f""" onclick="{oc}" """ if oc else ""

    # Render as an icon by default, or a button if specified in kwargs
    if kwargs.get("button"):
        return mark_safe(f"""<a class="btn btn-info btn-sm" href="{reverse(url)}"{oc}>Change Airport</a>""")
    else:
        if kwargs.get("text"):
            icon = html_generating.IconNode(['icon', 'bi-pencil-square']).render(context)
            return mark_safe(f"""<a href="{reverse(url)}"{oc} style="text-decoration:none;">{icon} {kwargs.get("text")}</a>""")
        else:
            # Link will just be an edit icon (with .visually-hidden text)
            icon = html_generating.IconNode(['icon', 'bi-pencil-square', 'text-info', 'title="Change Airport"']).render(context)
            return mark_safe(f"""<a href="{reverse(url)}"{oc}>{icon}</a>""")