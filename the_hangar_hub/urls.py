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
from the_hangar_hub.views import public_v, admin_v, airport_v, hh_subscription_v, infrastructure_v
from the_hangar_hub.views.application import app_mgmt_v, app_tenant_v, app_shared_v
from the_hangar_hub.views.maintenance import mx_mgmt_v, mx_tenant_v, mx_shared_v
from the_hangar_hub.views.rent import rent_mgmt_v, rent_tenant_v, rent_subscription_v

# Accessible to non-authenticated users
public_paths = [
    path('', public_v.home,                                          name='home'),
    path('styles', public_v.style_samples,                           name='style_samples'),
    path('airports', public_v.search,                                name='search'),
    path('airports/<slug:airport_identifier>', public_v.select,      name='select'),
    path('join/<invitation_code>', public_v.invitation_landing,      name='invitation_landing'),
]

# Accessible to developers and site administrators
administration_paths = [
    path('invitations', admin_v.invitation_dashboard,                         name='invitation_dashboard'),
    path('invitations/send', admin_v.send_invitation,                         name='send_invitation'),
]

# Airport-specific content
airport_paths = [
    path('<slug:airport_identifier>', airport_v.welcome,                                  name='welcome'),

    # HH SUBSCRIPTIONS
    path('<slug:airport_identifier>/claim', hh_subscription_v.claim_airport,                       name='claim'),
    path('<slug:airport_identifier>/subscriptions', hh_subscription_v.subscriptions,              name='subscriptions'),
    path('<slug:airport_identifier>/subscribe',  hh_subscription_v.subscribe, name='subscribe'),
    path('<slug:airport_identifier>/subscribe/fail',  hh_subscription_v.subscription_failure, name='subscription_failure'),
    path('<slug:airport_identifier>/subscribe/success',  hh_subscription_v.subscription_success, name='subscription_success'),

    path('<slug:airport_identifier>', airport_v.my_airport, name='airport'),
    path('<slug:airport_identifier>/stripe', airport_v.my_subscription, name='subscription'),
    path('<slug:airport_identifier>/update', airport_v.update_airport, name='update_airport'),
    path('<slug:airport_identifier>/upload/logo', airport_v.upload_logo, name='upload_logo'),
    path('<slug:airport_identifier>/assign', airport_v.add_manager, name='add_manager'),
    path('<slug:airport_identifier>/manager/update', airport_v.update_manager, name='update_manager'),
]


# Hangar Application Paths
application_paths = [

    # TENANT DASHBOARD
    path('dashboard', app_tenant_v.dashboard,      name='dashboard'),

    # FORM
    path('', app_tenant_v.form,                                               name='form'),
    path('<int:application_id>', app_tenant_v.form,                           name='resume'),
    path('<slug:airport_identifier>', app_tenant_v.form,                      name='airport_form'),
    path('save/<int:application_id>', app_tenant_v.save,                      name='save'),
    path('submit/<int:application_id>', app_tenant_v.submit,                  name='submit'),
    path('payment/<int:application_id>', app_tenant_v.record_payment,         name='record_payment'),

    # REVIEW SUBMISSIONS
    path('review/<int:application_id>', app_shared_v.review_application,      name='review'),
    path('change/<int:application_id>', app_shared_v.change_status,           name='change_status'),
    path('delete/<int:application_id>', app_shared_v.delete_application,           name='delete'),
    path('select/<int:application_id>', app_mgmt_v.select_application,           name='select'),
    path('review/<int:application_id>/submit', app_mgmt_v.submit_review, name='submit_review'),

    # AIRPORT PREFERENCES
    path('preferences/<slug:airport_identifier>', app_mgmt_v.preferences,        name='preferences'),
    path('preferences/<slug:airport_identifier>/save', app_mgmt_v.save_preferences,        name='save_preferences'),

    # APPLICATION/WAITLIST
    path('<slug:airport_identifier>/application/dashboard', app_mgmt_v.application_dashboard, name='mgmt_dashboard'),
    path('<slug:airport_identifier>/waitlist/prioritize', app_mgmt_v.change_wl_priority, name='change_wl_priority'),
    path('<slug:airport_identifier>/waitlist/index', app_mgmt_v.change_wl_index, name='change_wl_index'),
]


# Airport Manager Paths
infrastructure_paths = [
    # AIRPORT MANAGEMENT (building and hangar definitions/config)
    path('<slug:airport_identifier>/buildings', infrastructure_v.my_buildings,                       name='buildings'),
    path('<slug:airport_identifier>/buildings/add', infrastructure_v.add_building,                name='add_building'),
    path('<slug:airport_identifier>/buildings/<building_id>', infrastructure_v.my_hangars,           name='hangars'),
    path('<slug:airport_identifier>/buildings/<building_id>/add', infrastructure_v.add_hangar,    name='add_hangar'),
    path('<slug:airport_identifier>/hangar/delete', infrastructure_v.delete_hangar,    name='delete_hangar'),
    path('<slug:airport_identifier>/hangars/<slug:hangar_id>', infrastructure_v.one_hangar,                name='hangar'),
]

mx_paths = [
    # MAINTENANCE
    path('<slug:airport_identifier>/maintenance/request/comment/<int:request_id>', mx_shared_v.post_comment,  name='post_mx_comment'),

    # MAINTENANCE
    path('<slug:airport_identifier>/maintenance/request/comment/<int:request_id>', mx_shared_v.post_comment, name='post_mx_comment'),

    path('maintenance', mx_tenant_v.tenant_dashboard, name='mx_dashboard'),
    path('<slug:airport_identifier>/maintenance/request/<slug:hangar_id>', mx_tenant_v.tenant_request, name='mx_request_form'),
    path('<slug:airport_identifier>/maintenance/request/<slug:hangar_id>/post', mx_tenant_v.tenant_request_submit, name='submit_mx_request'),
    path('<slug:airport_identifier>/maintenance/request/view/<int:request_id>', mx_tenant_v.tenant_request_view, name='view_mx_request'),

    path('<slug:airport_identifier>/maintenance', mx_mgmt_v.manager_dashboard,  name='mx_dashboard'),
    path('<slug:airport_identifier>/maintenance/request/view/<int:request_id>', mx_mgmt_v.manager_request_view,  name='view_mx_request'),
    path('<slug:airport_identifier>/maintenance/request/priority/<int:request_id>', mx_mgmt_v.update_priority,  name='update_mx_priority'),
    path('<slug:airport_identifier>/maintenance/request/status/<int:request_id>', mx_mgmt_v.update_status,  name='update_mx_status'),
    path('<slug:airport_identifier>/maintenance/request/comment/visibility', mx_mgmt_v.update_visibility,  name='mx_comment_visibility'),
]

rent_paths = [
    path('<slug:airport_identifier>/hangars/<slug:hangar_id>/assign', rent_mgmt_v.add_tenant,     name='add_tenant'),

    path('<slug:airport_identifier>/hangar/<slug:hangar_id>', rent_tenant_v.my_hangar, name='hangar'),

    # Stripe Rent Subscription Management
    # path('<slug:airport_identifier>/rentals/invoice/create', rent_subscription.create_invoice,     name='create_invoice'),
    path('<slug:airport_identifier>/rentals/subscription/form', rent_subscription_v.get_subscription_form,     name='subscription_form'),
    path('<slug:airport_identifier>/rentals/subscription/create', rent_subscription_v.create_subscription,     name='create_subscription'),
    path('<slug:airport_identifier>/rentals/invoice/delete_draft', rent_subscription_v.delete_draft_invoice,     name='delete_draft_invoice'),

    # TENANT PAYMENT DASHBOARD
    path('dashboard', rent_tenant_v.payment_dashboard,  name='dashboard'),
    path('autopay/set', rent_tenant_v.set_auto_pay,  name='set_auto_pay'),

    # MANAGER PAYMENT ACTIONS

    # Rent Collection Dashboard
    path('<slug:airport_identifier>/dashboard', rent_mgmt_v.rent_collection_dashboard,  name='rent_collection_dashboard'),

    # Rental Invoices
    path('<slug:airport_identifier>/invoices/<int:rental_id>', rent_mgmt_v.rental_invoices,  name='rental_invoices'),
    path('<slug:airport_identifier>/invoices/<int:rental_id>/create', rent_mgmt_v.create_rental_invoice,  name='create_rental_invoice'),
    path('<slug:airport_identifier>/invoices/<int:rental_id>/update', rent_mgmt_v.update_rental_invoice,  name='update_rental_invoice'),

    # Refresh data from Stripe API
    path('<slug:airport_identifier>/rental/refresh', rent_subscription_v.refresh_rental_status,  name='refresh_rental_status_tbd'),
    path('<slug:airport_identifier>/rental/refresh/<int:rental_id>', rent_subscription_v.refresh_rental_status,  name='refresh_rental_status'),

]


urlpatterns = [
    # Django and Plugin URLs
    re_path('^admin/', admin.site.urls),
    re_path('^accounts/', include('allauth.urls')),
    re_path('^base/', include(('base.urls', 'base'), namespace='base')),
    re_path('^upload/', include(('base_upload.urls', 'base_upload'), namespace='upload')),
    re_path('^stripe/', include(('base_stripe.urls', 'base_stripe'), namespace='stripe')),

    re_path('', include((public_paths, 'the_hangar_hub'), namespace='public')),
    re_path('administration/', include((administration_paths, 'the_hangar_hub'), namespace='administration')),


    re_path('airport/', include((airport_paths, 'the_hangar_hub'), namespace='airport')),
    re_path('infrastructure/', include((infrastructure_paths, 'the_hangar_hub'), namespace='infrastructure')),
    re_path('application/', include((application_paths, 'the_hangar_hub'), namespace='application')),
    re_path('mx/', include((mx_paths, 'the_hangar_hub'), namespace='mx')),
    re_path('rent/', include((rent_paths, 'the_hangar_hub'), namespace='rent')),
]
