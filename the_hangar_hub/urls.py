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
from the_hangar_hub.views import *

app_paths = [
    path('', home, name='home'),

    path('airport', welcome, name='welcome'),
    path('airport/select', select_airport, name='select_airport'),
    path('airport/manage/<airport_identifier>', manage_airport, name='manage_airport'),
    path('airport/update', update_airport_data, name='update_airport_data'),
    path('airport/manager/add', add_airport_manager, name='add_airport_manager'),
    path('airport/invitation/accept/<verification_code>', accept_invitation, name='accept_invitation'),
    path('airport/invitation/accept', accept_invitation, name='invitation_link'),
]

urlpatterns = [
    # Django and Plugin URLs
    re_path('^admin/', admin.site.urls),
    re_path('^accounts/', include('allauth.urls')),
    re_path('^base/', include(('base.urls', 'base'), namespace='base')),

    re_path('', include((app_paths, 'the_hangar_hub'), namespace='hub')),
]
