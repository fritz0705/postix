import glob
import hashlib
import os

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from .settings import EventSettings


def record_balance():
    balance = 0
    for record in Record.objects.all():
        if record.type == "inflow":
            balance += record.amount
        elif record.type == "outflow":
            balance -= record.amount
    return balance


class RecordEntity(models.Model):
    """This class is the source or destination for records, for example "Bar 1", or "Unnamed Supplier"."""

    name = models.CharField(
        max_length=200, help_text='For example "Bar", or "Vereinstisch", …'
    )
    detail = models.CharField(
        max_length=200, help_text="For example the name of the bar, …"
    )

    class Meta:
        ordering = ("name", "detail")

    def __str__(self):
        return "{s.name}: {s.detail}".format(s=self)


class Record(models.Model):
    TYPES = (("inflow", _("Inflow")), ("outflow", _("Outflow")))
    type = models.CharField(max_length=20, choices=TYPES, verbose_name=_("Direction"))
    datetime = models.DateTimeField(
        verbose_name=_("Date"),
        help_text=_("Leave empty to use the current date and time."),
    )
    cash_movement = models.OneToOneField(
        to="core.CashMovement",
        on_delete=models.SET_NULL,
        related_name="record",
        null=True,
        blank=True,
    )
    entity = models.ForeignKey(
        RecordEntity,
        on_delete=models.PROTECT,
        related_name="records",
        verbose_name=_("Entity"),
        null=True,
        blank=True,
    )
    carrier = models.CharField(
        max_length=200, null=True, blank=True, verbose_name=_("Carrier")
    )
    amount = models.DecimalField(
        decimal_places=2, max_digits=10, verbose_name=_("Amount")
    )
    backoffice_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="records",
        verbose_name=_("Backoffice user"),
        on_delete=models.PROTECT,
    )
    is_balancing = models.BooleanField(
        default=False, verbose_name=_("Is a balancing record")
    )
    closes_session = models.BooleanField(
        default=False,
        verbose_name=_("Report closes session and contains additional pages"),
    )
    is_locked = models.BooleanField(default=False)
    data = models.TextField(null=True, blank=True)

    @property
    def checksum(self):
        if not self.pk:
            return ""
        checksum = hashlib.sha1()
        for attribute in [
            "type",
            "datetime",
            "cash_movement",
            "entity",
            "carrier",
            "amount",
            "is_balancing",
        ]:
            checksum.update(str(getattr(self, attribute, "")).encode())
        return checksum.hexdigest()

    @cached_property
    def export_data(self):
        is_special = (
            self.cash_movement
            and self.closes_session
            and self.cash_movement.session.cashdesk.handles_items
        )
        entity = entity_detail = ""
        if self.is_balancing:
            entity = str(_("Balancing"))
            entity_detail = str(_("Difference"))
        elif self.cash_movement:
            if (
                self.cash_movement.session.cashdesk
                and self.cash_movement.session.cashdesk.record_name
                and self.cash_movement.session.cashdesk.record_detail
            ):
                entity = self.cash_movement.session.cashdesk.record_name
                entity_detail = (
                    self.cash_movement.session.cashdesk.record_detail
                    + " (#{})".format(self.cash_movement.session.pk)
                )
            else:
                entity = "Kassensession"
                entity_detail = (
                    self.cash_movement.session.cashdesk.name
                    + " (#{})".format(self.cash_movement.session.pk)
                )
        elif self.entity:
            entity = self.entity.name
            entity_detail = self.entity.detail

        tz = timezone.get_current_timezone()
        date = self.datetime.astimezone(tz)
        return {
            "date": date.strftime("%d.%m.%Y"),
            "time": date.strftime("%H:%M:%S"),
            "direction": "Einnahme"
            if (is_special or self.type == "inflow")
            else "Ausgabe",
            "amount": "{0:,.2f}".format(self.amount).translate(
                str.maketrans(",.", ".,")
            ),
            "cashdesk_session": (
                self.cash_movement.session.pk
                if self.cash_movement and self.cash_movement.session
                else None
            ),
            "entity": entity,
            "entity_detail": entity_detail,
            "supervisor": (
                self.cash_movement.session.backoffice_user_after.get_full_name()
                if is_special
                else self.backoffice_user.get_full_name()
            )
            or "",
            "user": (
                (
                    self.cash_movement.session.user.get_full_name()
                    if self.cash_movement.session.user
                    else self.carrier
                )
                if is_special
                else self.named_carrier
            )
            or "",
            "checksum": self.checksum,
        }

    class Meta:
        ordering = ("datetime",)

    def __str__(self):
        return (
            self.datetime.strftime("Day %d %X")
            + " "
            + self.named_entity
            + " "
            + str(self.amount)
            + " EUR"
        )

    @property
    def named_entity(self):
        if self.cash_movement:
            return str(self.cash_movement.session.cashdesk or "")
        return str(self.entity or "")

    @property
    def named_carrier(self):
        if (
            self.cash_movement
            and self.cash_movement.session.user
            and self.cash_movement.session.cashdesk.ip_address
        ):
            return str(self.cash_movement.session.user.get_full_name())
        return self.carrier or ""

    def save(self, *args, **kwargs):
        if not self.datetime:
            self.datetime = now()
        super().save(*args, **kwargs)

    @property
    def record_path(self):
        base = default_storage.path("records")
        search = os.path.join(
            base,
            "{}_record_{}-*.pdf".format(EventSettings.get_solo().short_name, self.pk),
        )
        all_records = sorted(glob.glob(search))

        if all_records:
            return all_records[-1]

    def get_new_record_path(self) -> str:
        return os.path.join(
            "records",
            "{}_record_{}-{}.pdf".format(
                EventSettings.objects.get().short_name,
                self.pk,
                now().strftime("%Y%m%d-%H%M"),
            ),
        )
