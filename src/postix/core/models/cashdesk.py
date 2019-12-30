import string
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Union

from django.db import models
from django.db.models import Sum
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ugettext as _

from ..mixins import Exportable
from ..utils import devices
from ..utils.printing import CashdeskPrinter, DummyPrinter
from .base import Item, Product, TransactionPosition, TransactionPositionItem


def generate_key() -> str:
    return get_random_string(
        length=32, allowed_chars=string.ascii_letters + string.digits
    )


class Cashdesk(Exportable, models.Model):
    name = models.CharField(max_length=254)
    record_name = models.CharField(
        max_length=200,
        help_text='For example "Bar", or "Vereinstisch", or "Kassensession"',
        null=True,
        blank=True,
    )
    record_detail = models.CharField(
        max_length=200,
        help_text="For example the name of the bar. Leave empty for presale cashdesks.",
        null=True,
        blank=True,
    )
    ip_address = models.GenericIPAddressField(
        verbose_name=_("IP address"), null=True, blank=True
    )
    printer_queue_name = models.CharField(
        max_length=254,
        null=True,
        blank=True,
        verbose_name=_("Printer queue name"),
        help_text=_("The name configured in CUPS"),
    )
    is_active = models.BooleanField(default=True)
    printer_handles_drawer = models.BooleanField(
        default=True,
        verbose_name=_("Printer handles drawer"),
        help_text=_("Unset if the printer or drawer are broken."),
    )
    handles_items = models.BooleanField(default=True, verbose_name=_("Handles items"))

    def __str__(self) -> str:
        return self.name

    @property
    def printer(self) -> Union[CashdeskPrinter, DummyPrinter]:
        if self.printer_queue_name:
            return CashdeskPrinter(self.printer_queue_name, self)
        return DummyPrinter()

    def signal_open(self):
        for device in self.devices.all():
            device.open()

    def signal_next(self):
        for device in self.devices.all():
            device.next()

    def signal_close(self):
        for device in self.devices.all():
            device.close()

    def get_active_sessions(self) -> List:
        return [
            session
            for session in self.sessions.filter(end__isnull=True)
            if session.is_active()
        ]

    @cached_property
    def cash_balance(self):
        return (Decimal('-1.00') * (CashMovement.objects.filter(session__cashdesk=self).aggregate(s=Sum('cash'))['s'] or Decimal('0.00'))).quantize(Decimal('0.01'))


class CashdeskDeviceVariantChoices:
    DISPLAY = "display"
    DUMMY = "dummy"

    _choices = ((val, val) for val in [DISPLAY, DUMMY])


class CashdeskDevice(models.Model):
    variant = models.CharField(
        max_length=10, choices=CashdeskDeviceVariantChoices._choices
    )
    cashdesk = models.ForeignKey(
        to="Cashdesk", on_delete=models.CASCADE, related_name="devices"
    )
    target = models.CharField(
        max_length=100,
        verbose_name="Device endpoint",
        help_text="Address of any kind under which to reach the device.",
    )

    DEVICE_MAP = {
        CashdeskDeviceVariantChoices.DISPLAY: devices.OverheadDisplay,
        CashdeskDeviceVariantChoices.DUMMY: devices.DummyDevice,
    }

    def open(self):
        DeviceClass = self.DEVICE_MAP[self.variant]
        return DeviceClass(self.target).open()

    def next(self):
        DeviceClass = self.DEVICE_MAP[self.variant]
        return DeviceClass(self.target).next()

    def close(self):
        DeviceClass = self.DEVICE_MAP[self.variant]
        return DeviceClass(self.target).close()


class ActiveCashdeskSessionManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(start__lte=now())
            .filter(models.Q(end__gte=now()) | models.Q(end__isnull=True))
        )


class CashdeskSession(models.Model):
    cashdesk = models.ForeignKey(
        "Cashdesk", related_name="sessions", on_delete=models.PROTECT
    )
    user = models.ForeignKey("User", on_delete=models.PROTECT, null=True, blank=True)
    start = models.DateTimeField(
        default=now,
        verbose_name="Start of session",
        help_text="Default: time of creation.",
    )
    end = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="End of session",
        help_text="Only set if session has ended",
    )
    cash_after = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Cash in drawer after session",
    )
    backoffice_user_before = models.ForeignKey(
        "User",
        on_delete=models.PROTECT,
        related_name="supervised_session_starts",
        verbose_name="Backoffice operator before session",
    )
    backoffice_user_after = models.ForeignKey(
        "User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="supervised_session_ends",
        verbose_name="Backoffice operator after session",
    )
    api_token = models.CharField(
        max_length=254,
        default=generate_key,
        verbose_name="API token",
        help_text="Used for non-browser sessions. Generated automatically.",
    )
    comment = models.TextField(blank=True)

    objects = models.Manager()
    active = ActiveCashdeskSessionManager()

    def __str__(self) -> str:
        return "#{2} ({0} on {1})".format(self.user, self.cashdesk, self.pk)

    def is_active(self) -> bool:
        return (not self.start or self.start < now()) and not self.end

    def get_item_set(self) -> List[Item]:
        return [
            Item.objects.get(pk=pk)
            for pk in self.item_movements.order_by()
            .values_list("item", flat=True)
            .distinct()
        ]

    def get_current_items(self) -> List[Dict]:
        transactions = (
            TransactionPositionItem.objects.values("item")
            .filter(position__transaction__session=self)
            .exclude(position__type="reverse")
            .filter(position__reversed_by=None)
            .annotate(total=models.Sum("amount"))
        )
        item_movements = self.item_movements.values("item").annotate(
            total=models.Sum("amount")
        )

        transaction_dict = defaultdict(int)
        movement_dict = defaultdict(int)
        post_movement_dict = defaultdict(int)
        if self.end:
            post_movements = item_movements.filter(timestamp__gte=self.end)
            item_movements = item_movements.filter(timestamp__lt=self.end)
            for d in post_movements:
                post_movement_dict[d["item"]] += d["total"]

        for d in item_movements:
            movement_dict[d["item"]] += d["total"]
        for d in transactions:
            transaction_dict[d["item"]] += d["total"]

        return [
            {
                "item": item,
                "movements": movement_dict.get(item.pk, 0),
                "transactions": transaction_dict.get(item.pk, 0),
                "final_movements": -post_movement_dict.get(item.pk, 0)
                if self.end
                else 0,
                "total": movement_dict.get(item.pk, 0)
                + post_movement_dict.get(item.pk, 0)
                - transaction_dict.get(item.pk, 0),
            }
            for item in sorted(self.get_item_set(), key=lambda x: x.pk)
        ]

    @property
    def records(self):
        from postix.core.models.record import Record

        return Record.objects.filter(cash_movement__cashdesk_session=self)

    @property
    def cash_remaining(self) -> Decimal:
        return self.cash_before + self.get_cash_transaction_total()

    @property
    def final_cash_movement(self):
        movement = self.cash_movements.all().order_by("-timestamp").first()
        if (
            not self.end
            or not hasattr(movement, "record")
            or not movement.record.closes_session
        ):
            return None
        return movement

    def create_final_movement(self, carrier=None):
        movement = self.final_cash_movement
        if movement:
            if movement.record.is_locked:
                raise Exception(
                    _("Session has already been finalized and the record is locked.")
                )
        else:
            movement = CashMovement(session=self)
        movement.cash = -self.cash_after
        movement.backoffice_user = self.backoffice_user_after
        movement.save()
        movement.create_record(closes_session=True, carrier=carrier)
        return movement

    @property
    def cash_before(self) -> Decimal:
        qs = self.cash_movements.all()
        if self.end and self.final_cash_movement:
            qs = qs.exclude(pk=self.final_cash_movement.pk)
        return qs.aggregate(total=Sum("cash"))["total"] or Decimal("0.00")

    def get_cash_transaction_total(self) -> Decimal:
        return (
            TransactionPosition.objects.filter(transaction__session=self).aggregate(
                total=models.Sum("value")
            )["total"]
            or 0
        )

    def get_product_sales(self) -> List[Dict]:
        qs = TransactionPosition.objects.filter(transaction__session=self)
        result = []

        # Apparently, .values() does not support Func() expressions :(
        for p in (
            qs.order_by()
            .extra(select={"value_abs": "ABS(value)"})
            .values("product", "value_abs")
            .distinct()
        ):
            product = Product.objects.get(pk=p["product"])
            product_query = qs.filter(
                product=product, value__in=[p["value_abs"], -p["value_abs"]]
            )
            summary = {
                "product": product,
                "sales": product_query.filter(type="sell").count(),
                "presales": product_query.filter(type="redeem").count(),
                "reversals": product_query.filter(type="reverse").count(),
                "value_single": p["value_abs"],
            }
            summary["value_total"] = product_query.aggregate(s=Sum("value"))["s"] or 0
            result.append(summary)

        result = sorted(result, key=lambda entry: entry["product"].name)
        return result

    def request_resupply(self) -> None:
        TroubleshooterNotification.objects.create(
            session=self, modified_by=self.user, message="Requesting resupply"
        )

    def has_open_requests(self) -> bool:
        return TroubleshooterNotification.objects.active(session=self).exists()

    @property
    def is_latest_session(self) -> bool:
        return not self.cashdesk.sessions.filter(start__gt=self.start).exists()


class ItemMovement(models.Model):
    """ Instead of a through-table. Negative amounts indicate items moved out
    of a session, this mostly happens when a session is closed and all remaining
    items are removed and counted manually. """

    session = models.ForeignKey(
        "CashdeskSession",
        on_delete=models.PROTECT,
        related_name="item_movements",
        verbose_name="Session the item was involved in",
    )
    item = models.ForeignKey(
        "Item",
        on_delete=models.PROTECT,
        related_name="item_movements",
        verbose_name="Item moved to/from this session",
    )
    amount = models.IntegerField(
        help_text="Negative values indicate that items were taken out of a session. "
        "Mostly used when counting items after ending a session."
    )
    backoffice_user = models.ForeignKey(
        "User",
        on_delete=models.PROTECT,
        related_name="supervised_item_movements",
        verbose_name="Backoffice operator issuing movement",
    )
    timestamp = models.DateTimeField(default=now, editable=False)

    class Meta:
        ordering = ("timestamp",)

    def __str__(self) -> str:
        return "ItemMovement ({} {} at {})".format(
            self.amount, self.item, self.session.cashdesk.name
        )


class CashMovement(models.Model):
    """ Similar to ItemMovement """

    session = models.ForeignKey(
        "CashdeskSession",
        on_delete=models.PROTECT,
        related_name="cash_movements",
        verbose_name="Session the item was involved in",
    )
    cash = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Cash moved. Negative means taking it out of the session.",
    )
    backoffice_user = models.ForeignKey(
        "User",
        on_delete=models.PROTECT,
        related_name="supervised_cash_movements",
        verbose_name="Backoffice operator issuing movement",
    )
    timestamp = models.DateTimeField(default=now, editable=False)

    def create_record(self, closes_session=False, carrier=None):
        from postix.backoffice.report import generate_record
        from postix.core.models import Record

        record = getattr(self, "record", None)
        if not record:
            record = Record(cash_movement=self)
        record.amount = abs(self.cash)
        record.type = "inflow" if self.cash < 0 else "outflow"
        record.backoffice_user = self.backoffice_user
        record.is_balancing = False
        record.closes_session = closes_session
        record.carrier = carrier
        record.save()
        generate_record(record)
        return record


class NotificationsManager(models.Manager):
    def active(self, session=None) -> models.QuerySet:
        qs = self.get_queryset().filter(
            status=TroubleshooterNotification.STATUS_NEW,
            created__gt=now() - timedelta(minutes=10),
            session__end__isnull=True,
        )
        return qs.filter(session=session) if session else qs


class TroubleshooterNotification(models.Model):
    """
    Used for resupply requests at the moment.
    """

    STATUS_ACK = "ACK"
    STATUS_NEW = "New"
    STATUS_CHOICES = [(STATUS_ACK, STATUS_ACK), (STATUS_NEW, STATUS_NEW)]

    session = models.ForeignKey(
        "CashdeskSession",
        verbose_name="Cashdesk session initiating the notification",
        on_delete=models.PROTECT,
    )
    message = models.CharField(max_length=500)
    created = models.DateTimeField(default=now, editable=False)
    modified = models.DateTimeField(default=now)
    modified_by = models.ForeignKey("User", on_delete=models.PROTECT)
    status = models.CharField(choices=STATUS_CHOICES, default=STATUS_NEW, max_length=3)

    objects = NotificationsManager()

    def save(self, *args, **kwargs):
        self.modified = now()
        return super().save(*args, **kwargs)
