"""Management command to run standalone MQTT worker."""

from django.core.management.base import BaseCommand
from modules.mqtt_worker.worker import run_mqtt_worker


class Command(BaseCommand):
    help = "Run the CSI Smart Tech MQTT device integration worker"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting CSI Smart Tech MQTT Worker..."))
        try:
            run_mqtt_worker()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("MQTT Worker stopped by user."))
