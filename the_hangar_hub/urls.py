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
from the_hangar_hub.views import public, application, administration, airport, tenant, manage

public_paths = [
    path('', public.home,                                          name='home'),
    path('airports', public.search,                                name='search'),
    path('airports/<slug:airport_identifier>', public.select,      name='select'),
    path('join/<invitation_code>', public.invitation_landing,      name='invitation_landing'),
]

airport_paths = [
    path('<slug:airport_identifier>', airport.welcome,                                  name='welcome'),
]

admin_paths = [
    path('invitations', administration.invitation_dashboard,                         name='invitation_dashboard'),
    path('invitations/send', administration.send_invitation,                         name='send_invitation'),
]

airport_manager_paths = [
    path('<slug:airport_identifier>/claim', manage.claim_airport,                       name='claim'),
    path('<slug:airport_identifier>', manage.my_airport,                                name='airport'),
    path('<slug:airport_identifier>/update', manage.update_airport,                     name='update_airport'),
    path('<slug:airport_identifier>/assign', manage.add_manager,                        name='add_manager'),
    path('<slug:airport_identifier>/buildings', manage.my_buildings,                       name='buildings'),
    path('<slug:airport_identifier>/buildings/add', manage.add_building,                name='add_building'),
    path('<slug:airport_identifier>/buildings/<building_id>', manage.my_hangars,           name='hangars'),
    path('<slug:airport_identifier>/buildings/<building_id>/add', manage.add_hangar,    name='add_hangar'),
    path('<slug:airport_identifier>/hangars/<hangar_id>', manage.one_hangar,                name='hangar'),
    path('<slug:airport_identifier>/hangars/<hangar_id>/assign', manage.add_tenant,     name='add_tenant'),
]

airport_application_paths = [
    path('', application.form,                                               name='form'),
]

airport_tenant_paths = [
    path('<slug:airport_identifier>/tenant/hangar/<hangar_id>', tenant.my_hangar,  name='hangar'),
]

# app_paths = [
#     # Component actions
#     # path('airport/search', airport_search,                                              name='airport_search'),
#     # ToDo: These may not be relevant anymore:
#     path('airport/invitation/accept/<verification_code>', accept_invitation,            name='accept_invitation'),
#     path('airport/invitation/accept', accept_invitation,                                name='invitation_link'),
#     # Airport Views
#     path('<slug:airport_identifier>/welcome', welcome,                                 name='welcome'),
#     path('welcome', welcome,                                 name='welcome_x'),
#     path('airport/select_x', select_airport,                                              name='select_airport_x'),
# ]

urlpatterns = [
    # Django and Plugin URLs
    re_path('^admin/', admin.site.urls),
    re_path('^accounts/', include('allauth.urls')),
    re_path('^base/', include(('base.urls', 'base'), namespace='base')),

    re_path('', include((public_paths, 'the_hangar_hub'), namespace='hub')),
    re_path('airport/', include((airport_paths, 'the_hangar_hub'), namespace='airport')),
    re_path('manage/', include((airport_manager_paths, 'the_hangar_hub'), namespace='manage')),
    re_path('apply/', include((airport_application_paths, 'the_hangar_hub'), namespace='apply')),
    re_path('tenant/', include((airport_tenant_paths, 'the_hangar_hub'), namespace='tenant')),
    re_path('administration/', include((admin_paths, 'the_hangar_hub'), namespace='administration')),
]
