import os
import sys
from django.apps import AppConfig


class MqttWorkerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'modules.mqtt_worker'
    label = 'mqtt_worker'

    def ready(self):
        # Auto-start worker only when runserver or gunicorn/uvicorn is active (avoid running during tests or migrations)
        from django.conf import settings
        if getattr(settings, 'MQTT_AUTOSTART', False):
            # Check if running under runserver or uwsgi/gunicorn, not during migrate/makemigrations/test
            is_management_cmd = any(cmd in sys.argv for cmd in ['migrate', 'makemigrations', 'test', 'collectstatic', 'shell'])
            if not is_management_cmd:
                # Prevent running twice in Django dev reload main process
                if os.environ.get('RUN_MAIN') == 'true' or 'runserver' not in sys.argv:
                    from .worker import start_mqtt_worker_background
                    start_mqtt_worker_background()
