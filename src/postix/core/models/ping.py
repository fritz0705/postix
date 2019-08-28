from tempfile import TemporaryFile

import qrcode
import requests
from django.db import models
from django.utils.crypto import get_random_string
from django.utils.timezone import now

from .cashdesk import Cashdesk

MAX_LENGTH = 20


def generate_ping(cashdesk: Cashdesk) -> None:
    ping = Ping.objects.create()
    cashdesk.printer.print_image(ping.get_qr_code())


def generate_ping_secret():
    prefix = "/ping "
    return prefix + get_random_string(length=MAX_LENGTH - len(prefix))


class Ping(models.Model):
    pinged = models.DateTimeField(auto_now_add=True)
    ponged = models.DateTimeField(null=True, blank=True)
    secret = models.CharField(max_length=MAX_LENGTH, default=generate_ping_secret)
    synced = models.BooleanField(default=False)

    def get_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=5,
            border=4,
        )
        qr.add_data(self.secret)
        qr.make()
        f = TemporaryFile()
        img = qr.make_image()
        img.save(f)
        return f

    def pong(self):
        if not self.ponged:
            self.ponged = now()
            self.save()

    def sync(self, force=False):
        if self.synced and not force:
            return

        from .settings import EventSettings

        settings = EventSettings.get_solo()
        if not settings.queue_sync_url or not settings.queue_sync_token:
            return

        url = settings.queue_sync_url
        if not url.endswith("/"):
            url += "/"
        url += "pong"
        fmt = "%Y-%m-%d %H:%M:%S"
        response = requests.post(
            url,
            headers={"Authorization": settings.queue_sync_token},
            data={"ping": self.pinged.strftime(fmt), "pong": self.ponged.strftime(fmt)},
        )
        if response.status_code != 201:
            raise Exception(
                "Received non-201 status response from {}: {}".format(
                    url, response.status_code
                )
            )
        self.synced = True
        self.save()
