"""
URL configuration for the_hangar_hub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from the_hangar_hub.views import public, application, administration, airport, tenant, manage, maintenance

# Accessible to non-authenticated users
public_paths = [
    path('', public.home,                                          name='home'),
    path('styles', public.style_samples,                           name='style_samples'),
    path('airports', public.search,                                name='search'),
    path('airports/<slug:airport_identifier>', public.select,      name='select'),
    path('join/<invitation_code>', public.invitation_landing,      name='invitation_landing'),
]

# Accessible to developers and site administrators
administration_paths = [
    path('invitations', administration.invitation_dashboard,                         name='invitation_dashboard'),
    path('invitations/send', administration.send_invitation,                         name='send_invitation'),
]

# Hangar Application Paths
application_paths = [
    path('dashboard', application.dashboard,      name='dashboard'),

    # FORM
    path('', application.form,                                               name='form'),
    path('<int:application_id>', application.form,                           name='resume'),
    path('<slug:airport_identifier>', application.form,                      name='airport_form'),
    path('save/<int:application_id>', application.save,                      name='save'),
    path('submit/<int:application_id>', application.submit,                  name='submit'),

    # REVIEW SUBMISSIONS
    path('review/<int:application_id>', application.review_application,      name='review'),
    path('review/<int:application_id>/submit', application.submit_review,     name='submit_review'),
    path('change/<int:application_id>', application.change_status,           name='change_status'),
    path('delete/<int:application_id>', application.delete_application,           name='delete'),
    path('select/<int:application_id>', application.select_application,           name='select'),

    # AIRPORT PREFERENCES
    path('preferences/<slug:airport_identifier>', application.preferences,        name='preferences'),
    path('preferences/<slug:airport_identifier>/save', application.save_preferences,        name='save_preferences'),
]

# Airport-specific content
airport_paths = [
    path('<slug:airport_identifier>', airport.welcome,                                  name='welcome'),
    path('<slug:airport_identifier>/subscriptions', airport.subscriptions,              name='subscriptions'),
    path('<slug:airport_identifier>/subscribe',  airport.subscribe, name='subscribe'),
    path('<slug:airport_identifier>/subscribe/fail',  airport.subscriptions, name='subscription_failure'),
    path('<slug:airport_identifier>/subscribe/success',  airport.subscriptions, name='subscription_success'),
]


# Airport Manager Paths
manager_paths = [
    # AIRPORT MANAGEMENT (building and hangar definitions/config)
    path('<slug:airport_identifier>/claim', manage.claim_airport,                       name='claim'),
    path('<slug:airport_identifier>', manage.my_airport,                                name='airport'),
    path('<slug:airport_identifier>/update', manage.update_airport,                     name='update_airport'),
    path('<slug:airport_identifier>/upload/logo', manage.upload_logo,                     name='upload_logo'),
    path('<slug:airport_identifier>/assign', manage.add_manager,                        name='add_manager'),
    path('<slug:airport_identifier>/buildings', manage.my_buildings,                       name='buildings'),
    path('<slug:airport_identifier>/buildings/add', manage.add_building,                name='add_building'),
    path('<slug:airport_identifier>/buildings/<building_id>', manage.my_hangars,           name='hangars'),
    path('<slug:airport_identifier>/buildings/<building_id>/add', manage.add_hangar,    name='add_hangar'),
    path('<slug:airport_identifier>/hangars/<slug:hangar_id>', manage.one_hangar,                name='hangar'),
    path('<slug:airport_identifier>/hangars/<slug:hangar_id>/assign', manage.add_tenant,     name='add_tenant'),

    # APPLICATION/WAITLIST
    path('<slug:airport_identifier>/application/dashboard', manage.application_dashboard,     name='application_dashboard'),
    path('<slug:airport_identifier>/waitlist/prioritize', manage.change_wl_priority,     name='change_wl_priority'),
    path('<slug:airport_identifier>/waitlist/index', manage.change_wl_index,     name='change_wl_index'),
    
    # MAINTENANCE
    path('<slug:airport_identifier>/maintenance', maintenance.manager_dashboard,  name='mx_dashboard'),
    path('<slug:airport_identifier>/maintenance/request/view/<int:request_id>', maintenance.manager_request_view,  name='view_mx_request'),
    path('<slug:airport_identifier>/maintenance/request/priority/<int:request_id>', maintenance.update_priority,  name='update_mx_priority'),
    path('<slug:airport_identifier>/maintenance/request/status/<int:request_id>', maintenance.update_status,  name='update_mx_status'),
    path('<slug:airport_identifier>/maintenance/request/comment/<int:request_id>', maintenance.post_comment,  name='post_mx_comment'),
    path('<slug:airport_identifier>/maintenance/request/comment/visibility', maintenance.update_visibility,  name='mx_comment_visibility'),
]

# Hangar Tenant Paths
tenant_paths = [
    # MAINTENANCE
    path('maintenance', maintenance.tenant_dashboard,  name='mx_dashboard'),
    path('<slug:airport_identifier>/maintenance/request/<slug:hangar_id>', maintenance.tenant_request,  name='mx_request_form'),
    path('<slug:airport_identifier>/maintenance/request/<slug:hangar_id>/post', maintenance.tenant_request_submit,  name='submit_mx_request'),
    path('<slug:airport_identifier>/maintenance/request/view/<int:request_id>', maintenance.tenant_request_view,  name='view_mx_request'),
    path('<slug:airport_identifier>/maintenance/request/comment/<int:request_id>', maintenance.post_comment,  name='post_mx_comment'),

    # HANGAR
    path('<slug:airport_identifier>/hangar/<slug:hangar_id>', tenant.my_hangar,  name='hangar'),
]


urlpatterns = [
    # Django and Plugin URLs
    re_path('^admin/', admin.site.urls),
    re_path('^accounts/', include('allauth.urls')),
    re_path('^base/', include(('base.urls', 'base'), namespace='base')),
    re_path('^upload/', include(('base_upload.urls', 'base_upload'), namespace='upload')),

    re_path('', include((public_paths, 'the_hangar_hub'), namespace='hub')),
    re_path('airport/', include((airport_paths, 'the_hangar_hub'), namespace='airport')),
    re_path('manage/', include((manager_paths, 'the_hangar_hub'), namespace='manage')),
    re_path('apply/', include((application_paths, 'the_hangar_hub'), namespace='apply')),
    re_path('tenant/', include((tenant_paths, 'the_hangar_hub'), namespace='tenant')),
    re_path('administration/', include((administration_paths, 'the_hangar_hub'), namespace='administration')),
]
