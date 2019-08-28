import csv
import sys

from django.core.management.base import BaseCommand

from postix.core.models import Record


class Command(BaseCommand):
    help = "Export generated records as csv."

    def handle(self, *args, **kwargs):
        keys = [
            ("date", "Datum"),
            ("time", "Uhrzeit"),
            ("direction", "Richtung"),
            ("amount", "Betrag"),
            ("entity", "Quelle/Ziel"),
            ("entity_detail", "Detail"),
            ("cashdesk_session", "Kassensession"),
            ("supervisor", "Person"),
            ("user", "Einlieferer/Empfänger"),
            ("checksum", "Prüfsumme"),
        ]
        writer = csv.DictWriter(sys.stdout, fieldnames=[k[0] for k in keys])
        writer.writerow(dict(keys))
        for record in Record.objects.all():
            writer.writerow(record.export_data)
