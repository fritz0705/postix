import os
from decimal import Decimal
from typing import Union

from django.core.files.storage import default_storage
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Max, Sum
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from ..utils import round_decimal


class Transaction(models.Model):
    datetime = models.DateTimeField(auto_now_add=True)
    cash_given = models.DecimalField(null=True, max_digits=10, decimal_places=2)
    session = models.ForeignKey(
        "CashdeskSession", related_name="transactions", on_delete=models.PROTECT
    )
    receipt_id = models.PositiveIntegerField(null=True, blank=True, unique=True)

    def print_receipt(self, do_open_drawer: bool = True, session=None) -> None:
        (session or self.session).cashdesk.printer.print_receipt(self, do_open_drawer)

    @property
    def value(self) -> Decimal:
        return self.positions.aggregate(result=Sum("value"))["result"]

    @property
    def has_reversed_positions(self) -> bool:
        return any(tp.was_reversed() for tp in self.positions.all())

    @property
    def has_reversals(self) -> bool:
        return self.positions.filter(type="reverse").exists()

    @property
    def can_be_reversed(self) -> bool:
        return (not self.has_reversals) and (not self.has_reversed_positions)

    @property
    def has_invoice(self) -> bool:
        return bool(self.get_invoice_path())

    def get_invoice_path(self, allow_nonexistent: bool = False) -> Union[str, None]:
        if self.receipt_id:
            base = default_storage.path("invoices")
            path = os.path.join(base, "invoice_{:04d}.pdf".format(self.receipt_id))
            if allow_nonexistent or os.path.exists(path):
                return path
        return ""

    def set_receipt_id(self, retry: int = 0) -> None:
        try:
            self.receipt_id = 1 + (
                Transaction.objects.aggregate(m=Max("receipt_id"))["m"] or 0
            )
            self.save(update_fields=["receipt_id"])
        except Exception as e:
            if retry > 0:
                self.set_receipt_id(retry=retry - 1)
            else:
                raise e


class TransactionPosition(models.Model):
    TYPES = (
        ("redeem", "Presale redemption"),
        ("reverse", "Reversal"),
        ("sell", "Sale"),
    )

    transaction = models.ForeignKey(
        "Transaction", related_name="positions", on_delete=models.PROTECT
    )
    type = models.CharField(choices=TYPES, max_length=100)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(
        max_digits=4, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    tax_value = models.DecimalField(max_digits=10, decimal_places=2)
    product = models.ForeignKey(
        "Product", related_name="positions", on_delete=models.PROTECT
    )
    reverses = models.ForeignKey(
        "TransactionPosition",
        related_name="reversed_by",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    listentry = models.ForeignKey(
        "ListConstraintEntry",
        related_name="positions",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    preorder_position = models.ForeignKey(
        "PreorderPosition",
        related_name="transaction_positions",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    items = models.ManyToManyField(
        "Item", through="TransactionPositionItem", blank=True
    )
    authorized_by = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="authorized",
    )
    has_constraint_bypass = models.BooleanField(default=False)

    def calculate_tax(self) -> None:
        net_value = self.value * 100 / (100 + self.tax_rate)
        self.tax_value = round_decimal(self.value - net_value)

    def save(self, *args, **kwargs) -> None:
        if self.type == "reverse":
            self.product = self.reverses.product
            if self.value is None:
                self.value = -self.reverses.value
        if self.value is None:
            self.value = self.product.price
        if self.tax_rate is None:
            self.tax_rate = self.product.tax_rate

        self.calculate_tax()

        super(TransactionPosition, self).save(*args, **kwargs)

        if not self.items.exists():
            for pi in self.product.product_items.all().select_related("item"):
                TransactionPositionItem.objects.create(
                    position=self, item=pi.item, amount=pi.amount
                )

    def was_reversed(self) -> bool:
        if self.type == "reverse":
            return False

        return TransactionPosition.objects.filter(
            reverses=self, type="reverse"
        ).exists()


class Product(models.Model):
    name = models.CharField(max_length=254)
    receipt_name = models.CharField(max_length=28)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        verbose_name="Tax rate",
        help_text="in percent",
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    is_visible = models.BooleanField(default=True)
    is_admission = models.BooleanField(default=False)
    requires_authorization = models.BooleanField(default=False)
    items = models.ManyToManyField("Item", through="ProductItem", blank=True)
    priority = models.IntegerField(
        default=0,
        verbose_name="Priority",
        help_text="Will be used for sorting, high priorities come first.",
    )
    import_source_id = models.CharField(
        max_length=180, db_index=True, null=True, blank=True
    )

    def save(self, *args, **kwargs) -> None:
        if not self.receipt_name:
            self.receipt_name = self.name[:28]
        super().save(*args, **kwargs)

    @property
    def is_availably_by_time(self) -> bool:
        from . import TimeConstraint

        timeframes = TimeConstraint.objects.filter(products=self)
        if timeframes.exists():
            now = timezone.now()
            current_timeframes = timeframes.filter(start__lte=now, end__gte=now)
            if not current_timeframes.exists():
                return False

        return True

    @property
    def is_available(self) -> bool:
        from . import Quota

        quotas = Quota.objects.filter(products=self)
        if quotas.exists():
            all_quotas_available = all([quota.is_available for quota in quotas])
            if not all_quotas_available:
                return False

        return self.is_visible and self.is_availably_by_time

    @cached_property
    def preordered(self) -> int:
        return self.preorder_positions.filter(preorder__is_paid=True, preorder__is_canceled=False).count()

    @cached_property
    def redeemed_percent(self) -> Decimal:
        if self.preordered:
            return Decimal(self.amount_redeemed / self.preordered * 100).quantize(Decimal('0.01'))
        return Decimal('0.00')

    @cached_property
    def amount_sold(self) -> int:
        positive = self.positions.filter(type="sell").count()
        negative = (
            self.positions.filter(type="reverse")
            .exclude(preorder_position__isnull=False)
            .count()
        )
        return positive - negative

    @cached_property
    def amount_redeemed(self) -> int:
        positive = self.positions.filter(type="redeem").count()
        negative = (
            self.positions.filter(type="reverse")
            .exclude(preorder_position__isnull=True)
            .count()
        )
        return positive - negative

    @property
    def pack_list(self) -> str:
        result = []
        for item in self.product_items.all():
            if item.is_visible:
                if item.amount != 1:
                    result.append("{}x {}".format(item.amount, item.item.name))
                else:
                    result.append(item.item.name)
        return ", ".join(result)

    @property
    def needs_receipt(self) -> bool:
        return not self.product_items.filter(item__is_receipt=True).exists()

    def __str__(self) -> str:
        return self.name

    class Meta:
        ordering = ("-priority", "pk")


class Item(models.Model):
    name = models.CharField(max_length=254)
    description = models.TextField(blank=True)
    initial_stock = models.PositiveIntegerField()
    is_receipt = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name

    @cached_property
    def amount_sold(self) -> int:
        positive = self.transaction_position_items.filter(position__type="sell").count()
        negative = (
            self.transaction_position_items.filter(position__type="reverse")
            .exclude(position__preorder_position__isnull=False)
            .count()
        )
        return positive - negative

    @cached_property
    def amount_redeemed(self) -> int:
        positive = self.transaction_position_items.filter(
            position__type="redeem"
        ).count()
        negative = (
            self.transaction_position_items.filter(position__type="reverse")
            .exclude(position__preorder_position__isnull=True)
            .count()
        )
        return positive - negative


class ProductItem(models.Model):
    product = models.ForeignKey(
        "Product", on_delete=models.PROTECT, related_name="product_items"
    )
    item = models.ForeignKey(
        "Item", on_delete=models.PROTECT, related_name="product_items"
    )
    is_visible = models.BooleanField(
        default=True, help_text="If activated, this item will be shown in the frontend"
    )
    amount = models.IntegerField()


class TransactionPositionItem(models.Model):
    position = models.ForeignKey(
        "TransactionPosition",
        on_delete=models.PROTECT,
        related_name="transaction_position_items",
    )
    item = models.ForeignKey(
        "Item", on_delete=models.PROTECT, related_name="transaction_position_items"
    )
    amount = models.IntegerField()


class ItemSupplyPack(models.Model):
    STATES = (
        ("backoffice", _("In backoffice")),
        ("troubleshooter", _("With troubleshooter")),
        ("dissolved", _("Dissolved for other reasons")),
        ("used", _("Used to refill cash session")),
    )
    identifier = models.CharField(max_length=190, unique=True)
    item = models.ForeignKey(
        "Item", on_delete=models.PROTECT, related_name="supply_packs"
    )
    amount = models.IntegerField(default=50)
    state = models.CharField(max_length=190, choices=STATES)

    def __str__(self):
        return self.identifier


class ItemSupplyPackLog(models.Model):
    supply_pack = models.ForeignKey(
        ItemSupplyPack, related_name="logs", on_delete=models.PROTECT
    )
    new_state = models.CharField(max_length=190, choices=ItemSupplyPack.STATES)
    item_movement = models.ForeignKey(
        "ItemMovement",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name="Associated item movement",
    )
    user = models.ForeignKey(
        "User",
        on_delete=models.PROTECT,
        related_name="item_supply_logs",
        verbose_name="User issuing movement",
    )
    datetime = models.DateTimeField(auto_now_add=True, null=True, blank=True)
