"""
URL configuration for the_hangar_hub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path(f'', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path(f'', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path(f'blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from the_hangar_hub.views import public_v, admin_v, airport_v, hh_subscription_v, infrastructure_v
from the_hangar_hub.views.airport import ap_account_v, ap_welcome_v
from the_hangar_hub.views.application import app_mgmt_v, app_tenant_v, app_shared_v
from the_hangar_hub.views.maintenance import mx_mgmt_v, mx_tenant_v, mx_shared_v
from the_hangar_hub.views.rent import rent_mgmt_v, rent_tenant_v, rent_subscription_v
from django.conf import settings
from django.conf.urls.static import static

# To ensure consistent URL parameter names
airport = "<slug:airport_identifier>"
application = "<int:application_id>"
hangar = "<slug:hangar_id>"
rental = "<int:rental_agreement_id>"
request = "<int:request_id>"

# Accessible to non-authenticated users
public_paths = [
    path(f'', public_v.home,                                          name='home'),
    path(f'styles', public_v.style_samples,                           name='style_samples'),
    path(f'airports', public_v.search,                                name='search'),
    path(f'airports/{airport}', public_v.select,      name='select'),
    path(f'join/<invitation_code>', public_v.invitation_landing,      name='invitation_landing'),
]

# Accessible to developers and site administrators
developer_paths = [




    path(f'products', admin_v.products,                         name='products'),
    path(f'products/price/visibility', admin_v.price_visibility,                         name='price_visibility'),
    path(f'products/price/trial_days', admin_v.price_trial_days,                         name='trial_days'),
    path(f'products/price/attribute', admin_v.update_price_attr,                         name='update_price'),
    path(f'amenity/review', admin_v.amenity_review,                         name='amenity_review'),
    path(f'invitations', admin_v.invitation_dashboard,                         name='invitation_dashboard'),
    path(f'invitations/send', admin_v.send_invitation,                         name='send_invitation'),
]

# Airport-specific content
airport_paths = [
    path(f'{airport}', ap_welcome_v.welcome,                                  name='welcome'),
    path(f'{airport}/customize', ap_welcome_v.customize_content,                                  name='customize'),
    path(f'{airport}/amenities', ap_welcome_v.manage_amenities,                                  name='manage_amenity'),
    path(f'{airport}/logo', ap_welcome_v.logo,                                  name='logo'),
    path(f'{airport}/upload/logo', ap_welcome_v.upload_logo, name='upload_logo'),
    path(f'{airport}/blog/management', ap_welcome_v.manage_blog, name='manage_blog'),
    path(f'{airport}/blog/popup', ap_welcome_v.blog_popup, name='blog_popup'),
    path(f'{airport}/blog/post', ap_welcome_v.blog_post, name='blog_post'),
    path(f'{airport}/blog/upload/<int:entry_id>', ap_welcome_v.blog_upload, name='blog_reupload'),
    path(f'{airport}/blog/upload', ap_welcome_v.blog_upload, name='blog_upload'),
    path(f'{airport}/blog/update', ap_welcome_v.blog_update_form, name='blog_update'),
    path(f'{airport}/blog/delete', ap_welcome_v.blog_delete, name='blog_delete'),

    # HH SUBSCRIPTIONS
    path(f'{airport}/claim', hh_subscription_v.claim_airport,                       name='claim'),
    path(f'{airport}/subscriptions', hh_subscription_v.subscriptions,              name='subscriptions'),
    path(f'{airport}/subscribe',  hh_subscription_v.subscribe, name='subscribe'),
    path(f'{airport}/subscribe/fail',  hh_subscription_v.subscription_failure, name='subscription_failure'),
    path(f'{airport}/subscribe/success',  hh_subscription_v.subscription_success, name='subscription_success'),

    path(f'{airport}/manage', airport_v.my_airport, name='manage'),
    path(f'{airport}/stripe', ap_account_v.my_subscription, name='subscription'),
    path(f'{airport}/update', airport_v.update_airport, name='update_airport'),
    path(f'{airport}/assign', ap_account_v.add_manager, name='add_manager'),
    path(f'{airport}/manager/update', ap_account_v.update_manager, name='update_manager'),
]


# Hangar Application Paths
application_paths = [

    # TENANT DASHBOARD
    path(f'dashboard', app_tenant_v.dashboard,      name='dashboard'),

    # FORM
    path(f'', app_tenant_v.form,                                               name='form'),
    path(f'{application}', app_tenant_v.form,                           name='resume'),
    path(f'{airport}', app_tenant_v.form,                      name='airport_form'),
    path(f'save/{application}', app_tenant_v.save,                      name='save'),
    path(f'submit/{application}', app_tenant_v.submit,                  name='submit'),
    path(f'payment/{application}', app_tenant_v.record_payment,         name='record_payment'),

    # REVIEW SUBMISSIONS
    path(f'review/{application}', app_shared_v.review_application,      name='review'),
    path(f'change/{application}', app_shared_v.change_status,           name='change_status'),
    path(f'delete/{application}', app_shared_v.delete_application,           name='delete'),
    path(f'select/{application}', app_mgmt_v.select_application,           name='select'),
    path(f'review/{application}/submit', app_mgmt_v.submit_review, name='submit_review'),

    # AIRPORT PREFERENCES
    path(f'preferences/{airport}', app_mgmt_v.preferences,        name='preferences'),
    path(f'preferences/{airport}/save', app_mgmt_v.save_preferences,        name='save_preferences'),

    # APPLICATION/WAITLIST
    path(f'{airport}/application/dashboard', app_mgmt_v.application_dashboard, name='mgmt_dashboard'),
    path(f'{airport}/waitlist/prioritize', app_mgmt_v.change_wl_priority, name='change_wl_priority'),
    path(f'{airport}/waitlist/index', app_mgmt_v.change_wl_index, name='change_wl_index'),
]


# Airport Manager Paths
infrastructure_paths = [
    # AIRPORT MANAGEMENT (building and hangar definitions/config)
    path(f'{airport}/buildings', infrastructure_v.my_buildings,                       name='buildings'),
    path(f'{airport}/buildings/add', infrastructure_v.add_building,                name='add_building'),
    path(f'{airport}/buildings/delete', infrastructure_v.delete_building,            name='delete_building'),
    path(f'{airport}/buildings/<building_id>', infrastructure_v.my_hangars,           name='hangars'),
    path(f'{airport}/buildings/<building_id>/add', infrastructure_v.add_hangar,    name='add_hangar'),
    path(f'{airport}/hangar/delete', infrastructure_v.delete_hangar,    name='delete_hangar'),
    path(f'{airport}/hangars/{hangar}', infrastructure_v.one_hangar,                name='hangar'),
    path(f'{airport}/hangars/{hangar}/update', infrastructure_v.update_hangar,                name='update_hangar'),
]

mx_paths = [
    # MAINTENANCE
    path(f'{airport}/request/comment/{request}', mx_shared_v.post_comment, name='post_comment'),

    path(f'maintenance', mx_tenant_v.tenant_dashboard, name='tenant_dashboard'),
    path(f'{airport}/request/{hangar}', mx_tenant_v.tenant_request, name='request_form'),
    path(f'{airport}/request/{hangar}/post', mx_tenant_v.tenant_request_submit, name='submit_request'),
    path(f'{airport}/request/view/{request}', mx_tenant_v.tenant_request_view, name='tenant_view'),

    path(f'{airport}/maintenance', mx_mgmt_v.manager_dashboard,  name='mgmt_dashboard'),
    path(f'{airport}/manage/view/{request}', mx_mgmt_v.manager_request_view,  name='mgmt_view'),
    path(f'{airport}/request/priority/{request}', mx_mgmt_v.update_priority,  name='update_priority'),
    path(f'{airport}/request/status/{request}', mx_mgmt_v.update_status,  name='update_status'),
    path(f'{airport}/request/comment/visibility', mx_mgmt_v.update_visibility,  name='comment_visibility'),
    path(f'{airport}/scheduled/create', mx_mgmt_v.scheduled_mx_form,  name='scheduled_mx_form'),
]

rent_paths = [
    path(f'{airport}/rental/router', rent_subscription_v.rental_router,             name='rental_router'),
    path(f'{airport}/rental/router/{rental}', rent_subscription_v.rental_router,     name='rental_agreement_router'),

    path(f'{airport}/hangars/{hangar}/assign', rent_mgmt_v.add_tenant,     name='add_tenant'),

    path(f'{airport}/hangar/{hangar}', rent_tenant_v.my_hangar, name='hangar'),

    # Stripe Rent Subscription Management
    # path(f'{airport}/rentals/invoice/create', rent_subscription.create_invoice,     name='create_invoice'),
    path(f'{airport}/rentals/{rental}/subscribe/checkout', rent_subscription_v.rent_subscription_checkout,     name='subscription_checkout'),
    path(f'{airport}/rentals/{rental}/subscribe/email', rent_subscription_v.rent_subscription_email,     name='subscription_email'),

    
    path(f'{airport}/rentals/subscription/form', rent_subscription_v.get_subscription_form,     name='subscription_form'),

    # TENANT PAYMENT DASHBOARD
    path(f'dashboard', rent_tenant_v.payment_dashboard,  name='tenant_dashboard'),

    # MANAGER PAYMENT ACTIONS

    # Rent Collection Dashboard
    path(f'{airport}/dashboard', rent_mgmt_v.rent_collection_dashboard,  name='rent_collection_dashboard'),

    path(f'{airport}/agreement/terminate', rent_mgmt_v.terminate_rental_agreement,  name='terminate_rental_agreement'),

    # Rental Invoices
    path(f'{airport}/invoices/{rental}/invoices', rent_mgmt_v.rental_invoices,  name='rental_invoices'),
    path(f'{airport}/invoices/{rental}/create', rent_mgmt_v.create_rental_invoice,  name='create_rental_invoice'),
    path(f'{airport}/invoices/{rental}/update', rent_mgmt_v.update_rental_invoice,  name='update_rental_invoice'),

    # Refresh data from Stripe API
    path(f'{airport}/rental/refresh', rent_subscription_v.refresh_rental_status,  name='refresh_rental_status_tbd'),
    path(f'{airport}/rental/refresh/{rental}', rent_subscription_v.refresh_rental_status,  name='refresh_rental_status'),

]


urlpatterns = [
    # Django and Plugin URLs
    re_path(f'^admin/', admin.site.urls),
    re_path(f'^accounts/', include('allauth.urls')),
    re_path(f'^base/', include(('base.urls', 'base'), namespace='base')),
    re_path(f'^upload/', include(('base_upload.urls', 'base_upload'), namespace='upload')),
    re_path(f'^stripe/', include(('base_stripe.urls', 'base_stripe'), namespace='stripe')),
    re_path(f'^infotext/', include(('base_infotext.urls', 'base_infotext'), namespace='infotext')),

    re_path(f'', include((public_paths, 'the_hangar_hub'), namespace='public')),
    re_path(f'dev/', include((developer_paths, 'the_hangar_hub'), namespace='dev')),


    re_path(f'airport/', include((airport_paths, 'the_hangar_hub'), namespace='airport')),
    re_path(f'infrastructure/', include((infrastructure_paths, 'the_hangar_hub'), namespace='infrastructure')),
    re_path(f'application/', include((application_paths, 'the_hangar_hub'), namespace='application')),
    re_path(f'mx/', include((mx_paths, 'the_hangar_hub'), namespace='mx')),
    re_path(f'rent/', include((rent_paths, 'the_hangar_hub'), namespace='rent')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
