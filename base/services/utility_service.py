from django.db.models import Q
from base.models.utility.feature import Feature, FeatureToggle
from base.models.utility.error import Error
import re
import hashlib
import requests
import base64
from io import StringIO
from html.parser import HTMLParser
from datetime import datetime, timezone
from base.classes.util.app_data import Log, EnvHelper, AppData
import string
import secrets
from django.urls import reverse
from decimal import Decimal

log = Log()
env = EnvHelper()
app = AppData()


def generate_verification_code(length=30):
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(length))


def get_setting(property_name, default_value=None):
    """
    DEPRECATED
    """
    return env.get_setting(property_name, default_value)


# ===                  ===
# === APP/SUB-APP INFO ===
# ===                  ===


def get_primary_app_code():
    """
    DEPRECATED
    """
    return app.get_primary_app_code()


def sub_apps():
    """
    DEPRECATED
    """
    return app.sub_apps()


def get_app_options():
    """
    DEPRECATED
    """
    return app.get_app_options()


def get_app_code():
    """
    DEPRECATED
    """
    return app.get_app_code()


def is_in_primary_app():
    """
    DEPRECATED
    """
    return app.is_in_primary_app()


def get_sub_app_info(primary_app_code=None):
    """
    DEPRECATED
    """
    return app.get_sub_app_info(primary_app_code)


def set_sub_app_info(sub_app_info):
    """
    DEPRECATED
    """
    return app.set_sub_app_info(sub_app_info)


def get_app_name():
    """
    DEPRECATED
    """
    return app.get_app_name()


def get_app_version():
    """
    DEPRECATED
    """
    return app.get_app_version()


# ===                  ===
# === ENVIRONMENT DATA ===
# ===                  ===


def get_installed_plugins():
    """
    DEPRECATED
    """
    return env.installed_plugins


def get_environment():
    """
    DEPRECATED
    """
    return env.environment_code


def is_production():
    """
    DEPRECATED
    """
    return env.is_prod


def is_non_production():
    """
    DEPRECATED
    """
    return env.is_nonprod


def is_development():
    """
    DEPRECATED
    """
    return env.is_development


def get_static_content_url():
    """
    DEPRECATED
    """
    return env.static_content_url


def is_health_check():
    """
    DEPRECATED
    """
    return env.is_health_check


def get_request():
    """
    DEPRECATED
    """
    return env.request


def get_parameters():
    """
    DEPRECATED
    """
    return env.parameters


def get_browser():
    """
    DEPRECATED
    """
    return env.browser


def is_ajax():
    """
    DEPRECATED
    """
    return env.is_ajax


def pagination_sort_info(
        request, default_sort="id", default_order="asc", filter_name=None, reset_page=False, sort_tuple=True
):
    """
    Get the pagination sort order and page info.
    Sort info, page number, and filters are automatically tracked in the session.

    Parameters:
        request:        Django 'request' object (from view)
        default_sort:   Property/Column to sort by
        default_order:  asc or desc
        filter_name:    If view is filtering on a keyword string, or list of keyword strings, maintain that here as well
        reset_page:     True will force back to page 1 (i.e. new search/filter terms submitted)
        sort_tuple:     Return tuple rather than string as sort parameter. Allows multiple sort columns.
    Returns tuple: (sortby-string-or-tuple, page-number)
        sortby-string includes column and direction ('id', '-id')
        page-number is recommended page number (reset to 1 after sort change)

        if filter_name was given, tuple will have a third item:
            - if filter_name is a single item: a single string will be returned
            - if filter_name is a list of names, a dict of {name: value} will be returned
    """

    # Make sure filter name is a list (with 0, 1, or more items)
    if not filter_name:
        filter_name_list = []
    elif type(filter_name) is list:
        filter_name_list = filter_name
    else:
        filter_name_list = [filter_name]

    fn = env._get_cache_key()
    sort_var = f"{fn}-sort"
    order_var = f"{fn}-order"
    page_var = f"{fn}-page"
    filter_vars = {}
    for ff in filter_name_list:
        filter_vars[ff] = f"{fn}-filter-{ff}"

    # Get default sort, order, filter, page
    default_sort = env.get_session_variable(sort_var, default_sort)
    default_order = env.get_session_variable(order_var, default_order)
    default_page = env.get_session_variable(page_var, 1)

    default_filters = {}
    for ff in filter_name_list:
        default_filters[ff] = env.get_session_variable(filter_vars[ff], None)

    # Make default sort a tuple
    if type(default_sort) in [tuple, list]:
        default_sort = tuple(default_sort)
    elif default_sort:
        default_sort = (default_sort,)

    # Get values from parameters
    specified_sort = request.GET.get("sort", None)
    if specified_sort and "," in specified_sort:
        specified_sort = csv_to_list(specified_sort)
    specified_order = request.GET.get("order", None)
    page = request.GET.get("page", default_page)

    specified_filters = {}
    for ff in filter_name_list:
        if ff in request.GET:
            # Get parameter as a list
            as_list = request.GET.getlist(ff, None)

            # If filter is named with "list" then treat it as a list even if it has 0 or 1 value
            if "list" in ff:
                specified_filters[ff] = as_list
            # If not named as a list, but multiple values are present, return as a list
            elif as_list and len(as_list) > 1:
                specified_filters[ff] = as_list
            # Otherwise, return single value
            else:
                specified_filters[ff] = request.GET.get(ff, None)

        else:
            specified_filters[ff] = default_filters.get(ff)

    # Did the sort column change?
    if not specified_sort:
        sort_changed = False
    elif type(specified_sort) is list:
        sort_changed = specified_sort[0] and specified_sort[0] != default_sort[0]
        if len(specified_sort) > 1 and not sort_changed:
            if len(default_sort) < 2:
                sort_changed = True
            else:
                sort_changed = specified_sort[1] and specified_sort[1] != default_sort[1]
    else:
        sort_changed = specified_sort and specified_sort != default_sort[0]

    filter_changed = False
    for ff in filter_name_list:
        if ff in request.GET and specified_filters[ff] != default_filters[ff]:
            filter_changed = True

    # If sort is specified, adjust order as needed and return to page 1
    if specified_sort:
        page = 1

        # If sort has changed
        if sort_changed:
            # default to ascending order
            order = "asc"

            # make secondary sort by the previous selection
            try:
                if type(specified_sort) is list:
                    sort = tuple(specified_sort)
                else:
                    sort = (specified_sort,)

                if default_sort:
                    sort = sort + (default_sort[0],)

            except Exception as ee:
                Error.record(ee, f"Error updating default sort: {default_sort}")
                sort = (specified_sort,)

        # If sort has not changed
        elif specified_order:
            sort = default_sort
            order = specified_order

        # If sort stayed the same toggle between asc and desc
        else:
            sort = default_sort
            order = "asc" if default_order == "desc" else "desc"

    # If sort not specified, use default
    else:
        sort = default_sort
        order = default_order

    # If filter string changed, page will need to be reset
    if filter_changed:
        filter_strings = specified_filters
        page = 1
    else:
        filter_strings = default_filters

    if reset_page:
        page = 1

    # Remember sort preference
    env.set_session_variable(sort_var, sort)
    env.set_session_variable(order_var, order)
    env.set_session_variable(page_var, page)
    for ff in filter_name_list:
        env.set_session_variable(filter_vars[ff], filter_strings[ff])

    # Sortable column header taglib needs to know the last-sorted column
    # This assumes only one sorted dataset is being displayed at a time
    env.set_session_variable('base_last_secondary_sorted_column', sort[1] if type(sort) is tuple and len(sort) > 1 else sort)
    env.set_session_variable('base_last_sorted_column', sort[0] if type(sort) is tuple else sort)
    env.set_session_variable('base_last_sorted_direction', order)

    oo = "-" if order == "desc" else ""
    if type(sort) is tuple:
        sort_param = ()
        for vv in sort:
            sort_param += (f"{oo}{vv}",)

    elif sort:
        sort_param = (f"{oo}{sort}",)

    else:
        sort_param = None

    # If tuple not being used for sort param
    if not sort_tuple:
        sort_param = sort_param[0] if sort_param else None

    if filter_name:
        if len(filter_strings) == 1:
            return_val = sort_param, page, filter_strings[filter_name]
        else:
            return_val = sort_param, page, filter_strings
    else:
        return_val = sort_param, page

    return return_val


def store(value):
    """
    DEPRECATED
    """
    return env.store(value, ignore_levels=1)


def recall(alt=None):
    """
    DEPRECATED
    """
    return env.recall(alt, ignore_levels=1)


def _get_cache_key():
    """
    DEPRECATED
    """
    return env._get_cache_key(1)


def test_cache_key():
    """
    DEPRECATED
    """


def test_store_recall(value=None):
    """
    DEPRECATED
    """


def clear_page_scope():
    """
    DEPRECATED
    """
    return env.clear_page_scope()


# ===                   ===
# ===  FEATURE TOGGLES  ===
# ===                   ===


def feature_is_enabled(feature_code, force_query=False):
    """
    Is the given feature code active for this app?
    """
    return Feature.is_enabled(feature_code)


def get_feature(feature_code, force_query=False):
    return Feature.get(feature_code)


def get_features(force_query=False):
    """"""
    return Feature.get_feature_toggles(force_query)



# ===                   ===
# ===       LISTS       ===
# ===                   ===


def csv_to_list(src, convert_int=False):
    """Turn a string of comma-separated values into a python list"""
    result_list = None

    # If a list was already given, no conversion needed
    if type(src) is list or type(src) is None:
        result_list = src

    else:
        # Make sure we're working with a string
        src = str(src)

        # If the string "None" was given, return None
        if src == 'None':
            return None

        # Often, this is a python list that has been converted to a string at some point
        if src[0] == '[' and src[-1] == ']':
            src = src[1:-1]  # Remove brackets

        result_list = [ii.strip('"\' ') if type(ii) is str else ii for ii in src.split(',') if ii]

    # If converting list elements to a specified type
    if convert_int:
        return [int(ii) if type(ii) is str else ii for ii in result_list]
    # elif convert_<future-type>:
    #    return ...
    else:
        return result_list


def get_gravatar_image_src(email_address):
    """
        If the user has a Gravatar image, it will be used as their default profile image.
    """
    if env.get_setting("DISABLE_GRAVATAR"):
        return None

    if not email_address:
        return None

    log.trace([email_address])
    try:
        email = email_address.strip().lower()
        m = hashlib.md5()
        m.update(email.encode())
        email_hash = m.hexdigest()

        # ToDo: Provide an alt image so that a consistent response can indicate not having a Gravatar image
        alt_img = f"/images/no-id-photo.png"
        url = f"https://www.gravatar.com/avatar/{email_hash}?s=200&d={alt_img}"

        # Get the image data
        b64img = base64.b64encode(requests.get(url).content).decode()

        # If this is the default image, return None
        if b64img.startswith(
            "iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAMAAABrrFhUAAAAM1BMVEXn6+7g5em4xMvFz9XM1drk6Oy/ydCxvsa0wcn"
        ):
            return None

        return """data:image/jpg;base64,{0}""".format(b64img)

    except Exception as ee:
        log.error(f"Error getting Gravatar image: {str(ee)}")
        return None


def format_phone(phone_number, no_special_chars=False):
    """
    Format a phone number.
    """
    src = initial_string = str(phone_number) if phone_number else ''
    if ' ext ' in initial_string:
        src = initial_string.replace(' ext ', '')
    word_chars_only = re.sub(r'\W', "", src).upper()
    digits_only = re.sub(r'\D', "", src)

    # Remove unnecessary country code
    if len(digits_only) == 11 and digits_only.startswith('1'):
        digits_only = digits_only[1:]

    # Maybe it's an abbreviated campus number
    elif len(digits_only) == 5 and digits_only.startswith('5'):
        digits_only = "50372{}".format(digits_only)
    elif len(digits_only) == 7 and digits_only.startswith('725'):
        digits_only = "503{}".format(digits_only)

    # If a clean 10-digit number was given, split into the standard pieces
    # If longer than 10 digits, assume extra to be an extension
    if len(digits_only) > 10:
        if no_special_chars:
            return digits_only
        else:
            return f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:10]} ext {digits_only[10:]}"
    elif len(digits_only) == 10:
        if no_special_chars:
            return digits_only
        else:
            return f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:10]}"

    # If too short, just return it as-is. Maybe a real live human will figure it out.
    else:
        # If only 7-digits, return as a phone number with no area code
        if no_special_chars:
            return word_chars_only
        elif len(word_chars_only) == 7:
            return f"{word_chars_only[:3]}-{word_chars_only[3:]}"
        else:
            return initial_string.upper()

def format_decimal(amount, prefix="", use_commas=True, show_decimals=True):
    try:
        # Return empty-string for None values
        if amount is None:
            return None

        # Convert to Decimal
        amount_str = str(amount).replace(",", "").replace("$", "")
        amount_decimal = Decimal(amount_str)

        # Format the number as a string
        if use_commas and show_decimals:
            formatted_string = "{0:,.2f}".format(amount_decimal)
        elif use_commas:
            formatted_string = "{0:,.0f}".format(amount_decimal)
        elif show_decimals:
            formatted_string = "{0:.2f}".format(amount_decimal)
        else:
            formatted_string = "{0:.0f}".format(amount_decimal)

        # Prefix of None should be changed to ""
        if prefix is None:
            prefix = ""

        return f"{prefix}{formatted_string}"

    except Exception as ee:
        log.warn(f"Error formatting '{amount}' as decimal. {ee}")
        return ""


def decamelize(string):
    """Convert CamelCaseWord to camel_case_word"""
    result = ""
    ii = 0
    for xx in string:
        # if this is an upper case letter, add an underscore
        if xx != xx.lower() and ii != 0:
            result += '_'

        result += xx.lower()
        ii += 1

    return result


def camelize(string, cap_first_letter=True):
    """Convert camel_case_word to CamelCaseWord"""
    result = ""
    ii = 0
    cap_next_letter = cap_first_letter
    for xx in string:

        # if this is an underscore, capitalize next letter
        if xx == '_':
            cap_next_letter = True
            continue

        if cap_next_letter:
            result += xx.upper()
        else:
            result += xx.lower()

        cap_next_letter = False
        ii += 1

    return result


def strip_tags(html_string):
    # replace br with \n
    for br in ["<br>", "<br />", '<br style="clear:both;" />']:
        if f"{br}\n" in html_string:
            html_string = html_string.replace(f"{br}\n", "\n")
        if br in html_string:
            html_string = html_string.replace(br, "\n")
    if "\r" in html_string:
        html_string = html_string.replace("\r", "")
    s = MLStripper()
    s.feed(html_string)
    return s.get_data()


class MLStripper(HTMLParser):
    def error(self, message):
        pass

    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()
