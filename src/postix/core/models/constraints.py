from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class AbstractConstraint(models.Model):
    name = models.CharField(max_length=254)

    class Meta:
        abstract = True


class Quota(AbstractConstraint):
    size = models.PositiveIntegerField()
    products = models.ManyToManyField(
        "Product", verbose_name="Affected products", blank=True
    )

    @property
    def amount_sold(self):
        return sum([product.amount_sold for product in self.products.all()])

    @property
    def amount_available(self) -> int:
        return max(0, self.size - self.amount_sold)

    @property
    def is_available(self) -> bool:
        return bool(self.amount_available)

    def __str__(self) -> str:
        return "{} ({})".format(self.name, self.size)


class TimeConstraint(AbstractConstraint):
    start = models.DateTimeField(
        null=True, blank=True, verbose_name="Not available before"
    )
    end = models.DateTimeField(
        null=True, blank=True, verbose_name="Not available after"
    )
    products = models.ManyToManyField(
        "Product", verbose_name="Affected products", blank=True
    )

    def __str__(self) -> str:
        return "{} ({} - {})".format(self.name, self.start, self.end)


class ListConstraintProduct(models.Model):
    product = models.OneToOneField(
        "Product", on_delete=models.PROTECT, related_name="product_list_constraint"
    )
    constraint = models.ForeignKey(
        "ListConstraint", on_delete=models.PROTECT, related_name="product_constraints"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )


class ListConstraint(AbstractConstraint):
    products = models.ManyToManyField(
        "Product",
        verbose_name="Affected products",
        blank=True,
        through="ListConstraintProduct",
    )
    confidential = models.BooleanField(
        default=False,
        help_text="Confidential lists cannot be shown completely "
        "and only searched for substrings longer than "
        "3 letters for a maximum of 10 results.",
    )

    def __str__(self) -> str:
        return self.name


class ListConstraintEntry(models.Model):
    list = models.ForeignKey(
        "ListConstraint", related_name="entries", on_delete=models.PROTECT
    )
    name = models.CharField(max_length=254)
    identifier = models.CharField(max_length=254)

    @property
    def is_redeemed(self) -> bool:
        from postix.core.utils.checks import is_redeemed

        return is_redeemed(self)

    def __str__(self) -> str:
        return "{} ({}) – {}".format(self.name, self.identifier, self.list)

    class Meta:
        unique_together = (("list", "identifier"),)


class WarningConstraintProduct(models.Model):
    product = models.ForeignKey(
        "Product", on_delete=models.PROTECT, related_name="product_warning_constraints"
    )
    constraint = models.ForeignKey(
        "WarningConstraint",
        on_delete=models.PROTECT,
        related_name="product_constraints",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )


class WarningConstraint(AbstractConstraint):
    products = models.ManyToManyField(
        "Product",
        verbose_name="Affected products",
        blank=True,
        through="WarningConstraintProduct",
    )
    message = models.TextField()
