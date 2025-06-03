from base.classes.util.log import Log
import re

log = Log()


def get_max_field_length(field_name, model_instance):
    if model_instance and field_name:
        try:
            return model_instance._meta.get_field(field_name).max_length
        except Exception as eee:
            log.error(eee)
    elif not field_name:
        log.error("Field name not provided for max_length lookup")
    return None


def regex_search(string, pattern, flags=re.I):
    return bool(re.search(pattern, string, flags)) if string else None


def regex_replace(string, pattern, replacement):
    return re.sub(pattern, replacement, string) if string else None


def only_word_chars(string):
    return bool(re.match(r'^\w+$', string))


def contains_script(value):
    """Does the given value appear to contain a script tag (generic XSS checking)?"""

    # Empty values cannot have scripts
    if value is None:
        return False

    # Get value as a string and strip whitespace for comparisons
    string_value = str(value).strip()

    # Empty strings cannot have scripts
    if value == '':
        return False

    # Look for an obvious script tag
    script_tag = r'<\s?script'

    # Look for a src="javascript:..." tag
    script_src = r'<.*src\s?=\s?[\'"].*script.+'

    # Look for an on* event
    script_evt = r'<.*on\w+\s?=\s?[\'"].*'

    # Look for an iframe tag
    iframe_tag = r'<\s?iframe'

    if re.search(script_tag, string_value, re.I):
        return True
    if re.search(script_src, string_value, re.I):
        return True
    if re.search(script_evt, string_value, re.I):
        return True
    if re.search(iframe_tag, string_value, re.I):
        return True

    return False


def has_unlikely_characters(value, unlikely_characters='`!*=\\$%^[]{}<>;'):
    return value and any(x in value for x in unlikely_characters)


def is_email_address(email_string):
    if not email_string:
        return False
    if has_unlikely_characters(email_string):
        return False
    if '@' not in email_string:
        return False
    # ToDo: Better email validation
    return True
