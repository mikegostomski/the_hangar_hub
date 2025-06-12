from base.classes.util.log import Log
from base.classes.auth.session import Auth
from django.contrib.auth.models import User
from django.utils.functional import SimpleLazyObject

log = Log()

# ToDo: This can probably be deprecated and just use Auth() instead

def get_auth_instance():
    return Auth()


def is_logged_in():
    return get_auth_instance().is_logged_in()


def get_user_profile():
    """
    In non-production, admins can impersonate others for testing
    In production, developers can impersonate others for debugging
    """
    return Auth.current_user_profile()

def get_user():
    """
    In non-production, admins can impersonate others for testing
    In production, developers can impersonate others for debugging
    """
    return Auth.current_user()


def get_user_or_proxy_profile():
    auth = get_auth_instance()
    if auth.is_proxying():
        return auth.proxied_user
    else:
        return auth.get_current_user_profile()


def get_authenticated_user_profile():
    return get_auth_instance().authenticated_user


def lookup_user_profile(user_data, get_contact=False, get_authorities=False):
    """
    Get a UserProfile object for specified user.
    Lookups are cached for the duration of the request.
    """
    return Auth.lookup_user_profile(user_data, get_contact, get_authorities)


def has_authority(authority_list, use_impersonated=True):
    """
    Does the current user have the specified authority?
    If a list of authorities is given, only one of the authorities is required
    """
    if use_impersonated:
        return Auth.current_user_profile().has_authority(authority_list)
    else:
        return get_authenticated_user_profile().has_authority(authority_list)


def can_impersonate():
    return get_auth_instance().can_impersonate()


def start_impersonating(user_data):
    return get_auth_instance().set_impersonated_user(user_data)


def stop_impersonating():
    return get_auth_instance().set_impersonated_user(None)


def is_impersonating():
    return get_auth_instance().is_impersonating()

def is_django_user(object):
    return type(object) in [User, SimpleLazyObject]