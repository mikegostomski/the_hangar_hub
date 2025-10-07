import os
from celery import Celery

"""
celery -A the_hangar_hub worker --loglevel=info --pool=solo
"""

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'the_hangar_hub.settings')

app = Celery('the_hangar_hub')

# Load config from Django settings with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

"""
Run Celery Worker

Development (single terminal):
    bashcelery -A yourproject worker --loglevel=info
Development (with auto-reload on code changes):
    bashcelery -A yourproject worker --loglevel=info --pool=solo
    
    
Production (using systemd service):
Create /etc/systemd/system/celery.service:
    [Unit]
    Description=Celery Service
    After=network.target
    
    [Service]
    Type=forking
    User=www-data
    Group=www-data
    WorkingDirectory=/path/to/your/project
    Environment="PATH=/path/to/your/venv/bin"
    ExecStart=/path/to/your/venv/bin/celery -A yourproject worker --loglevel=info --detach --pidfile=/var/run/celery/worker.pid --logfile=/var/log/celery/worker.log
    PIDFile=/var/run/celery/worker.pid
    Restart=always
    
    [Install]
    WantedBy=multi-user.target

Enable and start:
    sudo systemctl daemon-reload
    sudo systemctl enable celery
    sudo systemctl start celery
    
    
    
Test Your Setup:
    celery -A the_hangar_hub inspect registered
    
    
    
Test a simple task in Django shell:

python manage.py shell

from the_hangar_hub.tasks import process_stripe_event
# Queue a task
result = process_stripe_event.delay(1)  # Use an actual event ID
print(result.id)  # Task ID

"""