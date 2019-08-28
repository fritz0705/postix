from django.core.management.base import BaseCommand

from postix.core.models import Ping


class Command(BaseCommand):
    help = "Run periodic tasks"

    def handle(self, *args, **options):
        for ping in Ping.objects.filter(synced=False, ponged__isnull=False).order_by(
            "ponged"
        ):
            ping.sync()
