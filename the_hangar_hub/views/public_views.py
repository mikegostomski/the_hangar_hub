from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from base.classes.util.env_helper import Log, EnvHelper
from base.services import auth_service

log = Log()
env = EnvHelper()

def home(request):
    return render(request, "the_hangar_hub/public/about.html")


def router(request):
    auth = auth_service.get_auth_instance()
    after_auth = env.get_session_variable("after_auth")
    if auth.is_logged_in():
        if after_auth:
            return redirect(after_auth)
        else:
            return redirect("hub:unspecified")
    else:
        return redirect("hub:home")

