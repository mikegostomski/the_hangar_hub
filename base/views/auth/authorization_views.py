from django.shortcuts import redirect, render
from django.http import HttpResponseForbidden
from ...services import utility_service, validation_service, message_service, error_service
from ...decorators import require_authority
from django.contrib.auth.models import User
from base.models.auth.authority import Authority
from base.models.auth.permission import Permission
from django.core.paginator import Paginator
from datetime import datetime
from django.db.models import Q
from base.classes.util.env_helper import Log, EnvHelper
from base.classes.auth.auth import Auth
import pytz


log = Log()
env = EnvHelper()


@require_authority('~security')
def manage_authorities(request):
    sort, page, keywords = utility_service.pagination_sort_info(request, 'code', filter_name='keywords')
    authorities = Authority.objects.order_by(*sort)
    paginator = Paginator(authorities, 50)
    authorities = paginator.get_page(page)

    return render(
        request, 'base/auth/manage_authorities.html',
        {
            'prefill': env.get_flash_scope('prefill', {}),
            'authorities': authorities,
        }
    )


@require_authority('~security')
def authorized_users(request, authority_id=None):
    """
    AJAX Request: Get users with specified authority
    """
    authority = Authority.objects.get(pk=authority_id) if authority_id else None
    if not authority:
        return HttpResponseForbidden()

    now = datetime.now(pytz.utc)
    permissions = Permission.objects.filter(authority__id=authority_id)
    permissions = permissions.filter(Q(effective_date__isnull=True) | Q(effective_date__lte=now))
    permissions = permissions.filter(Q(end_date__isnull=True) | Q(end_date__gt=now))
    permissions = permissions.order_by('user__last_name').order_by('user__first_name')

    return render(
        request, 'base/auth/authorized_users.html',
        {
            'authority': authority,
            'permissions': permissions,
        }
    )


@require_authority('~security')
def add_authority(request):
    has_issues = False
    try:
        code = request.POST.get('code')
        title = request.POST.get('title')
        description = request.POST.get('description')

        # Ignore empty submissions
        if not (code or title):
            log.warning("Empty form submission")
            return redirect('base:manage_authorities')

        if not code:
            message_service.post_error("Authority code is required")
            has_issues = True
        elif not validation_service.only_word_chars(code):
            message_service.post_error("Authority code may contain only word characters (A-Z and _)")
            has_issues = True

        if not has_issues:
            aa = Authority()
            aa.code = code[:30].lower()
            aa.title = title[:60]
            aa.description = description[:80]
            aa.save()
    except Exception as ee:
        error_service.unexpected_error("Unable to save authority", ee)
        has_issues = True

    if has_issues:
        env.set_flash_scope('prefill', {'code': code, 'title': title, 'description': description})

    return redirect('base:manage_authorities')


@require_authority('~security')
def manage_users(request):
    sort, page, keywords = utility_service.pagination_sort_info(
        request, ('last_name', 'first_name'), filter_name='keywords'
    )
    users = User.objects.order_by(*sort)
    paginator = Paginator(users, 50)
    users = paginator.get_page(page)

    return render(
        request, 'base/auth/manage_users.html',
        {
            'users': users,
        }
    )


@require_authority('~security')
def user_permissions(request, user_id):
    try:
        user = User.objects.get(pk=user_id)
        if not user:
            message_service.post_error("User not found")
            return redirect('base:manage_users')

        authorities = Authority.objects.order_by('title')
        authority_options = {aa.id: aa.title for aa in authorities}

        all_permissions = user.permissions.order_by('authority__title')

        permissions = []
        permission_history = []
        if all_permissions:
            for pp in all_permissions:
                if pp.is_history():
                    permission_history.append(pp)
                else:
                    permissions.append(pp)

    except Exception as ee:
        error_service.unexpected_error("Unable to retrieve user permissions", ee)
        return redirect('base:manage_users')

    return render(
        request, 'base/auth/user_permissions.html',
        {
            'user': user,
            'permissions': permissions,
            'permission_history': permission_history,
            'authority_options': authority_options,
        }
    )


@require_authority('~security')
def add_permission(request, user_id):
    try:
        user = User.objects.get(pk=user_id)
        if not user:
            message_service.post_error("User not found")
            return redirect('base:manage_users')

        authority = Authority.objects.get(pk=request.POST.get('authority_id'))
        if not authority:
            message_service.post_error("Authority not found")
            return redirect('base:user_permissions', user_id)

        pp = Permission()
        pp.authority = authority
        pp.user = user
        pp.save()

        Auth.audit(
            "C", "PERMISSIONS", f"Grant '{authority.code}' to {user.username}"
        )
    except Exception as ee:
        error_service.unexpected_error("Unable to grant user permission", ee)

    return redirect('base:user_permissions', user_id)


@require_authority('~security')
def delete_permission(request, permission_id):
    user_id = None
    try:
        pp = Permission.objects.get(pk=permission_id)
        if not pp:
            message_service.post_error("Permission not found")
            return redirect('base:manage_users')

        user_id = pp.user.id
        pp.terminate()

        Auth.audit(
            "D", "PERMISSIONS", f"Revoke '{pp.authority.code}' from {pp.user.username}"
        )

    except Exception as ee:
        error_service.unexpected_error("Unable to revoke user permission", ee)

    if user_id:
        return redirect('base:user_permissions', user_id)
    else:
        return redirect('base:manage_users')


@require_authority('~security')
def delete_user(request, user_id):
    try:
        user = User.objects.get(pk=user_id)
        if user:
            msg = f"Deleted account: {user.username}"
            user.delete()
            Auth.audit("D", "ACCOUNT", comments=msg)
        else:
            message_service.post_error("User was not found and could not be deleted.")
    except Exception as ee:
        error_service.unexpected_error("Unable to save authority", ee)

    return redirect('base:manage_users')
