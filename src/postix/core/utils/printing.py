import logging
import math
import subprocess
import time
from collections import defaultdict
from contextlib import suppress
from decimal import Decimal
from string import ascii_uppercase
from typing import List, Union

from django.utils import timezone
from django.utils.translation import ugettext as _
from PIL import Image

from postix.core.models import Transaction

SEPARATOR_CHAR = "\u2500"
SEPARATOR = "\u2500" * 42 + "\r\n"


class CashdeskPrinter:
    ESC = 0x1B

    def __init__(self, printer: str, cashdesk) -> None:
        self.printer = printer
        self.cashdesk = cashdesk

    @staticmethod
    def _format_number(number: Decimal) -> str:
        formatted_value = "{:.2f}".format(float(number))
        gap = " " * (7 - len(formatted_value))
        return gap + formatted_value

    def send(self, data: Union[str, bytes]) -> None:
        lpr = subprocess.Popen(
            ["/usr/bin/lpr", "-l", "-P", self.printer], stdin=subprocess.PIPE
        )
        if isinstance(data, str):
            try:
                data = data.encode("cp437")
            except UnicodeEncodeError:
                new_data = b""
                for char in data:
                    with suppress(UnicodeEncodeError):
                        new_data += char.encode("cp437")
                data = new_data
        lpr.stdin.write(data)
        lpr.stdin.close()
        time.sleep(0.1)

    def open_drawer(self) -> None:
        if self.cashdesk.printer_handles_drawer:
            self.send(bytearray([self.ESC, ord("p"), 48, 255, 255]))

    def cut_tape(self) -> None:
        self.send(bytearray([0x1D, 0x56, 66, 100]))

    def _build_log(self, transaction: Transaction) -> Union[None, str]:
        positions = transaction.positions.filter(authorized_by__isnull=False)
        print(positions)
        if not positions:
            return None

        receipt = bytearray([self.ESC, 0x61, 1]).decode()  # center text
        receipt += bytearray([self.ESC, 0x45, 1]).decode()  # emphasize
        receipt += _("Troubleshooter log") + "\r\n\r\n"
        receipt += bytearray([self.ESC, 0x45, 0]).decode()  # de-emphasize

        receipt += SEPARATOR

        receipt += bytearray([self.ESC, 0x61, 1]).decode()  # center text
        tz = timezone.get_current_timezone()
        receipt += (
            _("Date: {}").format(
                transaction.datetime.astimezone(tz).strftime("%d.%m.%Y %H:%M")
            )
            + "\r\n"
        )
        receipt += _("Transaction number: {}").format(transaction.id) + "\r\n"
        receipt += _("Cashdesk: {}").format(transaction.session.cashdesk.name) + "\r\n"
        receipt += _("Cashdesk session: {}").format(transaction.session.pk) + "\r\n"
        receipt += (
            _("Cashdesk user: {}").format(transaction.session.user.username) + "\r\n"
        )
        if transaction.receipt_id:
            receipt += _("Receipt number: {}").format(transaction.receipt_id) + "\r\n"
        receipt += "\r\n\r\n"

        receipt += bytearray([self.ESC, 0x61, 0]).decode()  # left-align text

        receipt += SEPARATOR
        for p in positions:
            receipt += _("Position type: {}").format(p.type) + "\r\n"
            receipt += _("Product: {}").format(p.product.name) + "\r\n"
            receipt += _("Price: {}").format(p.value) + "\r\n"
            receipt += _("Authorized by: {}").format(p.authorized_by.username) + "\r\n"
            receipt += _("What happened?") + ("\r\n" * 20)
            receipt += SEPARATOR
        return receipt

    def _build_receipt(self, transaction: Transaction) -> Union[None, str]:
        from postix.core.models import EventSettings

        settings = EventSettings.get_solo()
        total_sum = 0
        position_lines = list()
        tax_sums = defaultdict(int)
        tax_symbols = dict()

        positions = transaction.positions.exclude(type="redeem", value=Decimal("0.00"))

        if not positions.exists():
            return

        # Caution! This code assumes that cancellations are always made on transaction level
        cancellations = positions.filter(type="reverse")
        if cancellations.exists():
            cancels = cancellations.first().reverses.transaction
        else:
            cancels = None

        for position in transaction.positions.all():
            if position.value == 0:
                continue
            if not position.product.needs_receipt:
                continue
            total_sum += position.value
            tax_sums[position.tax_rate] += position.tax_value
            if position.tax_rate not in tax_symbols:
                tax_symbols[position.tax_rate] = ascii_uppercase[len(tax_sums) - 1]

            formatargs = {
                "product_name": position.product.name,
                "tax_str": tax_symbols[position.tax_rate],
                "gap": " " * (29 - len(position.product.name)),
                "price": self._format_number(position.value),
                "upgrade": _("Upgrade"),
                "upgradegap": " " * (29 - len(_("Upgrade"))),
            }
            if position.has_constraint_bypass:
                position_lines.append(" {product_name}".format(**formatargs))
                position_lines.append(
                    " {upgrade} ({tax_str}){upgradegap} {price}".format(**formatargs)
                )
            else:
                pos_str = " {product_name} ({tax_str}){gap} {price}".format(
                    **formatargs
                )
                position_lines.append(pos_str)
        total_taxes = sum(tax_sums.values())

        if not position_lines:
            return

        # Only get a new receipt ID after all early outs have passed
        # to make sure that we'll end up with actual consecutive numbers
        if not transaction.receipt_id:
            transaction.set_receipt_id(retry=3)
            is_copy = False
        else:
            is_copy = True

        receipt = bytearray([self.ESC, 0x61, 1]).decode()  # center text
        receipt += bytearray([self.ESC, 0x45, 1]).decode()  # emphasize
        receipt += settings.name + "\r\n\r\n"
        receipt += bytearray([self.ESC, 0x45, 0]).decode()  # de-emphasize
        if settings.receipt_address is not None:
            receipt += settings.receipt_address + "\r\n\r\n"

        if cancels:
            receipt += bytearray([self.ESC, 0x45, 1]).decode()  # emphasize
            receipt += _("Cancellation") + "\r\n"
            receipt += bytearray([self.ESC, 0x45, 0]).decode()  # de-emphasize
            receipt += _("for receipt {}").format(cancels.receipt_id) + "\r\n\r\n"

        if is_copy:
            receipt += bytearray([self.ESC, 0x45, 1]).decode()  # emphasize
            receipt += _("Receipt copy") + "\r\n\r\n"
            receipt += bytearray([self.ESC, 0x45, 0]).decode()  # de-emphasize

        receipt += SEPARATOR
        receipt += " {: <26}            EUR\r\n".format(_("Ticket"))
        receipt += SEPARATOR

        receipt += "\r\n".join(position_lines)
        receipt += "\r\n"
        receipt += SEPARATOR
        receipt += bytearray(
            [self.ESC, 0x61, 2]
        ).decode()  # right-align text (0 would be left-align)
        receipt += _("Net sum:  {}").format(
            self._format_number(total_sum - total_taxes)
        )
        receipt += "\r\n"

        for tax in sorted(list(tax_symbols), reverse=True):
            receipt += _("Tax {tax_rate}% ({tax_identifier}):  {tax_amount}").format(
                tax_rate=tax,
                tax_identifier=tax_symbols[tax],
                tax_amount=self._format_number(tax_sums[tax]),
            )
            receipt += "\r\n"

        receipt += _("Total:  {}").format(self._format_number(total_sum))
        receipt += "\r\n" * 3
        receipt += bytearray([self.ESC, 0x61, 1]).decode()  # center text
        receipt += settings.receipt_footer + "\r\n"
        tz = timezone.get_current_timezone()
        receipt += "{} {}\r\n".format(
            transaction.datetime.astimezone(tz).strftime("%d.%m.%Y %H:%M"),
            transaction.session.cashdesk.name,
        )
        receipt += _("Receipt number: {}").format(transaction.receipt_id)
        receipt += "\r\n\r\n\r\n"
        return receipt

    def print_receipt(
        self, transaction: Transaction, do_open_drawer: bool = True
    ) -> None:
        if do_open_drawer:
            self.open_drawer()
        receipt = self._build_receipt(transaction)
        log = self._build_log(transaction)

        if receipt:
            try:
                # self.send(image_tools.get_imagedata(settings.STATIC_ROOT + '/' + settings.EVENT_RECIPE_HEADER))
                self.send(receipt)
                self.cut_tape()
            except Exception as e:
                logging.getLogger("django").exception(
                    "Printing at {} failed: {}".format(self.printer, str(e))
                )

        if log:
            try:
                self.send(log)
                self.cut_tape()
            except Exception as e:
                logging.getLogger("django").exception(
                    "Printing at {} failed: {}".format(self.printer, str(e))
                )

    def _build_attendance(
        self, arrived: List["PreorderPosition"], not_arrived: List["PreorderPosition"]
    ):
        def shorten(line):
            if len(line) <= 40:
                return line
            return line[:39] + "..."

        def build_lines(position):
            information_lines = [
                "  " + l.strip() for l in position.information.split("\n") if l.strip()
            ]
            information_lines = [
                info.split("–", maxsplit=1)[-1].strip() for info in information_lines
            ]
            return information_lines

        from postix.core.models import EventSettings

        settings = EventSettings.get_solo()
        arrived_lines = [build_lines(position) for position in arrived]
        not_arrived_lines = [build_lines(position) for position in not_arrived]

        attendance = bytearray([self.ESC, 0x61, 1]).decode()  # center text
        attendance += bytearray([self.ESC, 0x45, 1]).decode()  # emphasize
        attendance += settings.name + " " + _("Attendance") + "\r\n"
        attendance += timezone.now().strftime("%Y-%m-%d %H:%M") + "\r\n"
        attendance += bytearray([self.ESC, 0x45, 0]).decode()  # de-emphasize

        if arrived_lines:
            arrived_lines = sum(arrived_lines, [])
            attendance += bytearray([self.ESC, 0x61, 1]).decode()  # center text
            attendance += "\r\n"
            count = "{count} ".format(count=len(arrived))
            seplen = (40 - len(count + _("Arrived"))) // 2
            attendance += (
                SEPARATOR_CHAR * seplen
                + " "
                + count
                + _("Arrived")
                + " "
                + SEPARATOR_CHAR * seplen
                + "\r\n"
            )
            attendance += bytearray(
                [self.ESC, 0x61, 0]
            ).decode()  # right-align text (2 would be left-align)
            attendance += "\r\n".join(arrived_lines)
            attendance += "\r\n"

        if not_arrived_lines:
            not_arrived_lines = sum(not_arrived_lines, [])
            attendance += bytearray([self.ESC, 0x61, 1]).decode()  # center text
            attendance += "\r\n"
            count = "{count} ".format(count=len(not_arrived))
            seplen = (40 - len(count + _("Not arrived"))) // 2
            attendance += (
                SEPARATOR_CHAR * seplen
                + " "
                + count
                + _("Not arrived")
                + " "
                + SEPARATOR_CHAR * seplen
                + "\r\n"
            )
            attendance += bytearray(
                [self.ESC, 0x61, 2]
            ).decode()  # right-align text (0 would be left-align)
            attendance += "\r\n".join(not_arrived_lines)
            attendance += "\r\n"

        attendance += bytearray([self.ESC, 0x61, 1]).decode()  # center text
        attendance += "\r\n"
        return attendance

    def print_attendance(
        self, arrived: List["PreorderPosition"], not_arrived: List["PreorderPosition"]
    ):
        attendance = self._build_attendance(arrived, not_arrived)
        if attendance:
            try:
                self.send(attendance)
                self.cut_tape()
            except Exception as e:
                logging.getLogger("django").exception(
                    "Printing at {} failed: {}".format(self.printer, str(e))
                )

    def print_text(self, text: str, centered=True, cut_tape=True) -> None:
        center = bytearray([self.ESC, 0x61, 1]).decode()  # center text
        left_align = bytearray(
            [self.ESC, 0x61, 0]
        ).decode()  # left-align text (0 would be left-align)
        print_text = ""
        if centered:
            print_text += center
        print_text += text.replace("\n", "\r\n") + left_align
        self.send(print_text)
        if cut_tape:
            self.cut_tape()

    def _get_pixel_value(
        self, outer_x, outer_y, inner_x, inner_y, total_x, total_y, image
    ):
        pixel_value = 0
        for square_y in range(8):
            x = outer_x * 3 + inner_x
            y = outer_y * 24 + inner_y * 8 + square_y
            px = 0
            if y < total_y and x < total_x:
                px = int(not bool(image[x, y]))
            pixel_value += px * 2 ** (7 - square_y)
        return int(pixel_value)

    def print_image(self, fileish):
        image = Image.open(fileish)

        image = image.convert("1")
        imagedata = image.load()
        (width, height) = image.size

        width_rounded_up = math.ceil(width / 3) * 3
        byte_count = width_rounded_up // 256
        bit_count = width_rounded_up % 256

        print_data = [self.ESC, ord("3"), 1]  # Set line spacing to 24 dots

        for line_y in range(
            math.ceil(height / 24)
        ):  # One "line" of image data is 24 px
            print_data.extend([self.ESC, ord("*"), 33])  # Set mode to bitmap, 24 dots
            print_data.extend([bit_count, byte_count])  # Specify data to be printed

            for line_x in range(
                math.ceil(width / 3)
            ):  # We write 3 x (3 x 8) pixels at once
                for inner_x in range(3):
                    for inner_y in range(3):
                        print_data.append(
                            self._get_pixel_value(
                                line_x,
                                line_y,
                                inner_x,
                                inner_y,
                                width,
                                height,
                                imagedata,
                            )
                        )
            print_data.extend([ord("\n"), ord("\r")])  # Newline

        print_data.extend([ord("\n"), ord("\r")])  # Newline
        print_data.extend([self.ESC, ord("3"), 30])  # Set linespacing back to normal

        array = bytearray(print_data)
        self.send(array)
        self.cut_tape()


class DummyPrinter:
    def __init__(self, printer=None, cashdesk=None, *args, **kwargs) -> None:
        self.cashdesk = cashdesk
        self.logger = logging.getLogger("django")

    def send(self, data) -> None:
        self.logger.info("[DummyPrinter] Received data: {}".format(data))

    def open_drawer(self) -> None:
        self.logger.info("[DummyPrinter] Opened drawer")

    def cut_tape(self) -> None:
        self.logger.info("[DummyPrinter] Cut tape")

    def print_receipt(
        self, transaction: Transaction, do_open_drawer: bool = True
    ) -> Union[str, None]:
        receipt = CashdeskPrinter("", self.cashdesk)._build_receipt(transaction)
        if receipt is not None:
            self.logger.info("[DummyPrinter] Printed receipt:\n{}".format(receipt))
        log = CashdeskPrinter("", self.cashdesk)._build_log(transaction)
        if log is not None:
            self.logger.info("[DummyPrinter] Printed log entry:\n{}".format(log))
        return receipt

    def print_attendance(
        self, arrived: List["PreorderPosition"], not_arrived: List["PreorderPosition"]
    ):
        arrivals = CashdeskPrinter("", self.cashdesk)._build_attendance(
            arrived, not_arrived
        )
        if arrivals is not None:
            self.logger.info("[DummyPrinter] Printed arrivals:\n{}".format(arrivals))
        return arrivals

    def print_image(self, fileish):
        self.logger.info("[DummyPrinter] Printed image")

    def print_text(
        self, text: str, centered: bool = True, cut_tape: bool = True
    ) -> None:
        self.send(text)
