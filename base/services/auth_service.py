from base.classes.util.log import Log
from base.classes.auth.auth import Auth

log = Log()


def get_auth_instance():
    return Auth()


def is_logged_in():
    return get_auth_instance().is_logged_in()


def get_user():
    """
    In non-production, admins can impersonate others for testing
    In production, developers can impersonate others for debugging
    """
    return get_auth_instance().get_user()


def get_user_or_proxy():
    auth = get_auth_instance()
    if auth.is_proxying():
        return auth.proxied_user
    else:
        return auth.get_user()


def get_authenticated_user():
    return get_auth_instance().authenticated_user


def has_authority(authority_list, use_impersonated=True):
    """
    Does the current user have the specified authority?
    If a list of authorities is given, only one of the authorities is required
    """
    if use_impersonated:
        return get_user().has_authority(authority_list)
    else:
        return get_authenticated_user().has_authority(authority_list)


def can_impersonate():
    return get_auth_instance().can_impersonate()


def start_impersonating(user_data):
    return get_auth_instance().set_impersonated_user(user_data)


def stop_impersonating():
    return get_auth_instance().set_impersonated_user(None)


def is_impersonating():
    return get_auth_instance().is_impersonating()
