from django.core.management.base import BaseCommand

from postix.core.models import Cashdesk, Ping


class Command(BaseCommand):
    help = "Generates and prints a ping at the cashdesk of the given pk (the first one otherwise)"

    def add_arguments(self, parser):
        parser.add_argument("cashdesk", default=None)

    def handle(self, *args, **kwargs):
        if kwargs["cashdesk"]:
            cashdesk = Cashdesk.objects.get(pk=kwargs["cashdesk"])
        else:
            cashdesk = Cashdesk.objects.first()

        ping = Ping.objects.create()
        cashdesk.printer.print_image(ping.get_qr_code())
