#
#   All template tags provided by the Base plugin are registered in this file.
#   For browse-ability, all processing happens outside this file.
#

from django import template
from base.models import Feature, Variable
from base.services import utility_service, auth_service, date_service, validation_service
from base.templatetags.tag_processing import html_generating, static_content
from django.urls import reverse
from django.utils.html import mark_safe
from django.template import TemplateSyntaxError
import time
from base.classes.util.app_data import Log, EnvHelper, AppData

log = Log()
env = EnvHelper()
app = AppData()

register = template.Library()


# # # # # # # # # # # # # # # # # # #
# UTILITY CATEGORY
# # # # # # # # # # # # # # # # # # #


@register.filter
def get(p_dict, p_key):
    return p_dict.get(p_key) if p_dict else None


@register.filter
def mod(n, d):
    if d == 0:
        return None
    return n % d


@register.filter
def collect(p_list, p_attr):
    """
    Given a list of objects, return a list of specific attribute values
    Example: collect(course_detail_list, "crn") -- would return a list of CRNs
    """
    return [xx.get(p_attr) if type(xx) is dict else getattr(xx, p_attr) for xx in p_list] if p_list else []


@register.filter
def maxlen(model_instance, field_name):
    """
    Given a model and field, return the max allowed length of that field
    """
    return validation_service.get_max_field_length(field_name, model_instance)


@register.simple_tag(takes_context=True)
def absolute_url(context, *args, **kwargs):
    if args:
        reverse_args = args[1:] if len(args) > 1 else None
        return f"{env.absolute_root_url}{reverse(args[0], args=reverse_args)}"
    else:
        return env.absolute_root_url


@register.simple_tag()
def flash_variable(*args, **kwargs):
    var = kwargs.get('var', args[0] if args else None)
    alt = kwargs.get('alt', args[1] if args and len(args) >= 2 else None)
    return env.get_flash_scope(var, alt)


@register.simple_tag()
def app_code():
    return app.get_app_code()


@register.simple_tag()
def app_name():
    return env.get_setting('APP_NAME')


@register.simple_tag()
def app_version():
    return app.get_app_version()


@register.filter
def has_plugin(plugin_name, true_false):
    """
    Check if application does/does not have specified custom plugin installed

    'mjg_infotext'|has_plugin:True   - Is the infotext plugin installed?
    'mjg_infotext'|has_plugin:False  - Is the infotext plugin NOT installed?
    """
    has_it = plugin_name in env.installed_plugins
    if true_false and has_it:
        return True
    elif (not true_false) and (not has_it):
        return True
    else:
        return False


@register.simple_tag()
def setting_value(setting_name, default_value=None):
    return env.get_setting(setting_name, default_value)


@register.filter
def get_setting(setting_name, default_value=None):
    """Get setting with default value. Usable in an IF or FOR tag"""
    return env.get_setting(setting_name, default_value)


@register.simple_tag(takes_context=True)
def set_var(context, *args, **kwargs):
    context[args[0]] = args[1]
    return ''


@register.simple_tag(takes_context=True)
def decode(context, *args):
    """
    Given an ID, return it's label from a dict of options.
    Optional third argument is a default value

    Ex:  {% decode department_code department_options %}
         {% decode 'CS' department_options %}
         {% decode 'N$^&' department_options 'Invalid Department' %}
    """
    value = args[1].get(args[0])
    if value is None and len(args) == 3:
        return args[2]
    return value


@register.simple_tag
def humanize(*args):
    # Humanize a datetime ("x seconds ago", "last week", "two years ago", ...)
    return date_service.humanize(args[0])


@register.inclusion_tag('base/components/humanized_date.html')
def humanized_date(*args, **kwargs):
    return {"dt": args[0], **kwargs}


@register.simple_tag
def format_phone(*args):
    # Phone could be in one arg, or split (area, phone, ext)
    return utility_service.format_phone(''.join([x for x in args if x]))


@register.simple_tag
def format_decimal(*args, **kwargs):
    number = args[0]
    if number is None or number == "":
        return ""

    # Allow some formatting options
    prefix = kwargs["prefix"] if "prefix" in kwargs and kwargs["prefix"] else ""
    use_commas = "comma" not in kwargs or bool(kwargs["comma"])
    show_decimals = "decimal" not in kwargs or bool(kwargs["decimal"])

    d = utility_service.format_decimal(args[0], prefix=prefix, use_commas=use_commas, show_decimals=show_decimals)

    # Return empty-string for None values
    return d if d is not None else ""


@register.simple_tag
def format_currency(*args, **kwargs):
    kwargs.update({'prefix': '$'})
    return format_decimal(*args, **kwargs)


@register.filter
def feature(feature_code, true_false):
    """
    Check if feature is enabled/disabled

    'my_feature'|feature:True   - Is feature enabled?
    'my_feature'|feature:False  - Is feature disabled?
    """
    is_enabled = Feature.is_enabled(feature_code)
    if true_false and is_enabled:
        return True
    elif (not true_false) and (not is_enabled):
        return True
    else:
        return False


@register.filter
def variable(variable_code, default_value):
    """
    Get value of variable

    'my_var'|variable:'unknown'
    """
    return Variable.get_value(variable_code, default_value)


# # # # # # # # # # # # # # # # # # #
# AUTHENTICATION CATEGORY
# # # # # # # # # # # # # # # # # # #


@register.filter
def has_authority(authority_code, true_false):
    """
    Check if current user does/does not have permission

    'admin'|has_authority:True   - Does user have admin?
    'admin'|has_authority:False  - Does user not have admin?

    'admin,infotext'|has_authority:True - Can provide csv list of authorities
    """
    has_it = auth_service.has_authority(authority_code)
    if true_false and has_it:
        return True
    elif (not true_false) and (not has_it):
        return True
    else:
        return False


@register.simple_tag(takes_context=True)
def check_admin_menu(context, *args, **kwargs):
    # All power users see the admin menu
    admin_menu_roles = []

    # Other custom plugins may include items for specific roles other than power-user roles
    for admin_link in context['plugin_admin_links']:
        if 'authorities' in admin_link:
            plus = utility_service.csv_to_list(admin_link['authorities'])
            admin_menu_roles.extend(plus if plus else [])

    has_it = auth_service.has_authority(admin_menu_roles)
    var_name = args[0] if len(args) > 0 else 'admin_menu'
    context[f"has_{var_name}"] = has_it
    context[f"does_not_have_{var_name}"] = not has_it
    return ''

# # # # # # # # # # # # # # # # # # #
# STATIC CONTENT CATEGORY
# # # # # # # # # # # # # # # # # # #


@register.simple_tag
def static_content_url():
    return env.static_content_url


@register.simple_tag
def jquery(*args, **kwargs):
    return static_content.jquery(*args, **kwargs)


@register.simple_tag
def bootstrap(*args, **kwargs):
    return static_content.bootstrap(*args, **kwargs)


@register.simple_tag
def font_awesome(*args, **kwargs):
    return static_content.font_awesome(*args, **kwargs)


@register.simple_tag
def icon_library(*args, **kwargs):
    return static_content.icon_library(*args, **kwargs)


@register.simple_tag
def datatables(*args, **kwargs):
    return static_content.datatables(*args, **kwargs)


@register.simple_tag
def jquery_confirm(*args, **kwargs):
    return mark_safe(static_content.jquery_confirm(*args, **kwargs))


@register.simple_tag
def chosen(*args, **kwargs):
    return static_content.chosen(*args, **kwargs)


@register.simple_tag
def tom_select(*args, **kwargs):
    return static_content.tom_select(*args, **kwargs)


@register.simple_tag
def cdn_js(*args, **kwargs):
    return static_content.cdn_js(*args, **kwargs)


@register.simple_tag
def cdn_css(*args, **kwargs):
    return static_content.cdn_css(*args, **kwargs)


@register.tag()
def image(parser, token):
    return html_generating.ImageNode(token.split_contents())


# # # # # # # # # # # # # # # # # # #
# HTML-GENERATING CATEGORY
# # # # # # # # # # # # # # # # # # #

@register.simple_tag()
def required():
    return mark_safe(""" <span class="required" title="required" aria-hidden="true">*</span><span class="visually-hidden">required field</span>""")


@register.inclusion_tag('base/components/pagination.html')
def pagination(paginated_results):
    """Example: {%pagination polls%}"""
    return html_generating.pagination(paginated_results)


@register.tag()
def sortable_th(parser, token):
    """Sortable <th> that works with server-side pagination"""
    return html_generating.SortableThNode(token.split_contents())


@register.tag()
def fa(parser, token):
    """Render a screen-reader-friendly FontAwesome4 icon"""
    return html_generating.FaNode(token.split_contents())


@register.tag()
def icon(parser, token):
    """
    Render a screen-reader-friendly icon.
    Originally written to transition from FontAwesome to Bootstrap Icons
    Might leave to handle both indefinitely, or even include others (BoxIcons?)
    """
    return html_generating.IconNode(token.split_contents())


@register.tag()
def select_menu(parser, token):
    return html_generating.SelectNode(token.split_contents())


@register.tag()
def js_alert(parser, token):
    """
    Simple jquery-confirm alert
    """
    tokens = token.split_contents()
    try:
        nodelist = parser.parse((f"end_{tokens[0]}",))
        parser.delete_first_token()
    except TemplateSyntaxError:
        nodelist = None

    return html_generating.JsAlert(nodelist, tokens)


@register.tag()
def js_confirm(parser, token):
    """
    Simple jquery-confirm confirmation box
    """
    tokens = token.split_contents()
    try:
        nodelist = parser.parse((f"end_{tokens[0]}",))
        parser.delete_first_token()
    except TemplateSyntaxError:
        nodelist = None

    return html_generating.JsConfirm(nodelist, tokens)


@register.tag()
def js_prompt(parser, token):
    """
    Simple jquery-confirm prompt for input
    {%js_prompt icon="bi-comment" title="Tell Me..." callback="my_action"%}
    """
    tokens = token.split_contents()
    try:
        nodelist = parser.parse((f"end_{tokens[0]}",))
        parser.delete_first_token()
    except TemplateSyntaxError:
        nodelist = None

    return html_generating.JsPrompt(nodelist, tokens)


@register.tag()
def accordion_item(parser, token):
    """
    Add an item to an accordion
    Example:
        <div class="accordion" id="accordion">
            {%accordion_item icon="bi-pencil-square" heading="Make Changes" collapsed=False%}
                ... HTML content goes here ...
            {%end_accordion_item%}
            {%accordion_item heading="Something else..."%}
                ... HTML content goes here ...
            {%end_accordion_item%}
        </div>

        Attributes:
            heading [REQUIRED] = Item heading text

            accordian_id [Required-ish] = ID of the accordion (required if container ID is not "#accordion")

            item_id = [OPTIONAL] ID for this item. Randomly generated if not given.
            icon = [OPTIONAL] fa|bi icon-class(es).  ("fa|bi" and "-fw" are included by default)
            collapsed = [OPTIONAL] Collapse item on page load? [True]/False
    """
    tokens = token.split_contents()
    try:
        nodelist = parser.parse((f"end_{tokens[0]}",))
        parser.delete_first_token()
    except TemplateSyntaxError:
        nodelist = None

    return html_generating.AccordionItem(nodelist, tokens)


@register.tag()
def popup(parser, token):
    """
    Create a popup "window"
    """
    tokens = token.split_contents()
    try:
        nodelist = parser.parse((f"end_{tokens[0]}",))
        parser.delete_first_token()
    except TemplateSyntaxError:
        nodelist = None

    return html_generating.Popup(nodelist, tokens)



@register.inclusion_tag("base/components/_smokescreen_spinner.html", takes_context=True)
def smokescreen_spinner(context, *args, **kwargs):
# def smokescreen_spinner(context, parser, token):
    """
    Smokescreen over full page while message spins...

    Attributes:
        - name: Unique (for the page) name for this spinner
        - message: Message to display (defaults to "Processing...")
        - icon: bi-gear, bi-hypnotize, bi-yin-yang, etc
        - class: Class name(s) to append to the spinner div
        - style: Styles to append to the spinner div
        - show: Show the smokescreen and spinner on page load? (True/False)

    Includes functions to show and hide the smokescreen-spinner:
        - show_{{name}}();
        - hide_{{name}}();

    Examples:
        {%smokescreen_spinner "sample_spinner" "Sampling..."%}
        {%smokescreen_spinner name='sample_spinner' message="Sampling" icon="bi-yin-yang" class="text-danger"%}
    """
    model = context.flatten()

    # Original tag took two positional arguments
    spinner_name = spinner_message = None

    # Check for positional arguments
    if args:
        spinner_name = args[0]
        if len(args) > 1:
            spinner_message = args[1]

    # Check for keyword args
    if kwargs:
        spinner_name = kwargs.get("name", spinner_name)
        spinner_message = kwargs.get("message", spinner_message)

    model.update({
        "spinner_name": spinner_name,
        "spinner_message": spinner_message,
        "spinner_icon": kwargs.get("icon", "bi-gear"),
        "spinner_class": kwargs.get("class", False),
        "spinner_style": kwargs.get("style", False),
        "spinner_show": kwargs.get("show", False),
    })

    return model


@register.tag()
def header_nav_menu_item(parser, token):
    """Example:  """
    return html_generating.HeaderNavMenuItem(token.split_contents())


@register.tag()
def header_nav_tab(parser, token):
    """Example:  """
    return html_generating.HeaderNavTab(token.split_contents())


@register.simple_tag()
def posted_message_birth_date():
    return int(time.time())
