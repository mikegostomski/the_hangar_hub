from django.shortcuts import render
from ..services import date_service
import time
from datetime import datetime, timezone
from base.classes.util.app_data import Log, EnvHelper, AppData

log = Log()
env = EnvHelper()
app = AppData()


def messages(request):
    return render(
        request,
        'base/template/standard/messages/messages.html',
        {'message_birth_date': int(time.time())}
    )


def status_page(request):
    session_data = {
        'expiry_seconds': request.session.get_expiry_age(),
        'expiry_description': date_service.seconds_to_duration_description(request.session.get_expiry_age())
    }
    return render(
        request, 'base/status_page.html',
        {
            'dev_test_content': int(time.time()),
            'server_time': datetime.now(timezone.utc),
            'session_data': session_data,
            'installed_plugins': env.installed_plugins,
        }
    )

