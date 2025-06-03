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
from the_hangar_hub.views import public_views

app_paths = [
    path('', public_views.home, name='home'),
]

urlpatterns = [
    # Django and Plugin URLs
    re_path('^admin/', admin.site.urls),
    re_path('^accounts/', include('allauth.urls')),
    re_path('^base/', include(('base.urls', 'base'), namespace='base')),

    re_path('', include((app_paths, 'the_hangar_hub'), namespace='hub')),
]
