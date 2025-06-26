from django.urls import path

from . import views

urlpatterns = [
    # For now, use the test page as default
    path('status', views.status_page, name='status'),

    # Messages
    path('messages', views.messages, name='messages'),

    # Authentication
    path('router', views.post_login_handler, name='post_login_handler'),
    path('login/then', views.login_then_next, name='login_then'),

    # Authorization
    path('auth/authorities', views.manage_authorities, name='manage_authorities'),
    path('auth/authorities/add', views.add_authority, name='add_authority'),
    path('auth/authorized/<int:authority_id>', views.authorized_users, name='authorized_users'),
    path('auth/authorized', views.authorized_users, name='authorized_users_tbd'),
    path('auth/users', views.manage_users, name='manage_users'),
    path('auth/user/permissions/<int:user_id>', views.user_permissions, name='user_permissions'),
    path('auth/user/permissions/<int:user_id>/add', views.add_permission, name='add_permission'),
    path('auth/user/permissions/<int:permission_id>/delete', views.delete_permission, name='delete_permission'),
    path('auth/user/delete/<int:user_id>', views.delete_user, name='delete_user'),

    # Contacts
    path('contact/list', views.contact_list, name='contact_list'),
    path('contact/refresh', views.refresh_contact, name='refresh_contact'),
    path('contact/form', views.contact_form, name='contact_form'),
    path('contact/profile', views.profile, name='profile'),
    path('contact/update/contact', views.update_contact, name='update_contact'),
    path('contact/update/phone', views.update_phone, name='update_phone'),
    path('contact/update/address', views.update_address, name='update_address'),

    # Referrals
    path('referral/dashboard', views.referral_dashboard, name='referral_dashboard'),
    path('referral/generate', views.generate_referral_code, name='generate_referral_code'),

    # Feature Toggles
    path('features', views.feature_list, name='features'),
    path('add_feature', views.add_feature, name='add_feature'),
    path('modify_feature', views.modify_feature, name='modify_feature'),
    path('delete_feature', views.delete_feature, name='delete_feature'),

    # Audit Events
    path('audit', views.audit_list, name='audit'),
    path('audit_xss', views.audit_xss_attempts, name='xss_list'),
    path('audit_xss_review', views.audit_xss_review_attempt, name='xss_dismiss'),
    path('xss', views.xss_prevention, name='xss_block'),
    path('xss_lock', views.xss_lock, name='xss_lock'),

    # Error logs
    path("errors", views.error_list, name="errors"),
    path("error_status", views.error_status, name="error_status"),
    path("error_status/ignore/<int:error_id>", views.ignore_similar, name="error_ignore"),

    # Enhancement Requests
    path("enhancement_requests", views.enhancement_requests, name="enhancement_requests"),


    # # Testing pages
    # path('test', views.test_status, name='test'),
    # path('versions', views.test_versions, name='versions'),
    # path('session', views.test_session, name='session'),
    # path('email', views.email_test_page, name='email'),

    # # Utility Views
    # path('validate/date', views.validate_date_format, name='validate_date_format'),
    # path('format/phone_number', views.format_phone_number, name='format_phone_number'),

    # # Data Export
    path('export', views.export_db, name='export_db'),
    path('export/menu', views.fixture_export_menu, name='fixture_export_menu'),
    path('export/action', views.fixture_export_action, name='fixture_export'),

    # Authentication and CAS login/logout endpoints
    path('stop_impersonating', views.stop_impersonating, name='stop_impersonating'),
    path('start_impersonating', views.start_impersonating, name='start_impersonating'),
    path('proxy_search', views.proxy_search, name='proxy_search'),

]
