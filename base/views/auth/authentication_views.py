from django.shortcuts import redirect, render
from django.http import HttpResponseForbidden, HttpResponse
from ...services import auth_service, error_service
from ...decorators import require_impersonation_authority, require_authentication
from base.classes.util.env_helper import Log, EnvHelper


log = Log()
env = EnvHelper()


def stop_impersonating(request):
    """
    To stop impersonating, the session will be cleared.
    Therefore, any proxy selected while impersonating will also be removed.
    """
    log.trace()
    auth_service.stop_impersonating()
    next_destination = request.GET.get('next', request.META.get('HTTP_REFERER'))
    try:
        return redirect(next_destination)
    except Exception as ee:
        error_service.record(ee, next_destination)
    return redirect('/')


@require_impersonation_authority()
def start_impersonating(request):
    """
    Handle the impersonation form and redirect to home page
    """
    log.trace()
    impersonation_data = request.POST.get('impersonation_data')
    auth_service.start_impersonating(impersonation_data)
    next_destination = request.GET.get('next', request.META.get('HTTP_REFERER'))
    try:
        return redirect(next_destination)
    except Exception as ee:
        error_service.record(ee, next_destination)
    return redirect('/')


@require_impersonation_authority()
def proxy_search(request):
    """
    When a proxy attempt fails, offer a user search screen
    """
    log.trace()
    found = None

    if request.method == 'POST' and request.POST.get('proxy_info'):
        pass

    # elif request.method == 'POST' and request.POST.get('search_info'):
    #     # Look up user from given data
    #     found = User(request.POST.get('search_info'))

    return render(
        request, 'auth/proxy_search.html',
        {'found': found}
    )


@require_authentication()
def post_login_handler(request):
    next_url = env.get_session_variable("after_auth_url", "/")
    env.set_session_variable("after_auth_url", None)
    return redirect(next_url)
