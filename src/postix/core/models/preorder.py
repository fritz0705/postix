from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext as _


class Preorder(models.Model):
    order_code = models.CharField(max_length=254, db_index=True)
    is_paid = models.BooleanField(default=False)
    is_canceled = models.BooleanField(default=False)
    warning_text = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.order_code


class PreorderPosition(models.Model):
    preorder = models.ForeignKey(
        Preorder, related_name="positions", on_delete=models.PROTECT
    )
    secret = models.CharField(max_length=254, db_index=True, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    product = models.ForeignKey(
        "Product", related_name="preorder_positions", on_delete=models.PROTECT
    )
    # The following field is only used for locking purposes, do not use it otherwise.
    # Please see comment in redeem_preorder_ticket for more information
    last_transaction = models.IntegerField(null=True, blank=True)
    information = models.CharField(max_length=1000, null=True, blank=True)

    def __str__(self) -> str:
        return "{}-{}".format(self.preorder.order_code, self.secret[:10])

    @property
    def is_redeemed(self) -> bool:
        from ..utils.checks import is_redeemed

        return is_redeemed(self)

    @property
    def is_paid(self) -> bool:
        return self.preorder.is_paid

    @property
    def is_canceled(self) -> bool:
        return self.preorder.is_canceled

    @property
    def product_name(self) -> str:
        return self.product.name

    @property
    def pack_list(self) -> str:
        return self.product.pack_list

    @property
    def redemption_message(self) -> str:
        from . import TransactionPosition

        if self.is_redeemed:
            last_r = TransactionPosition.objects.filter(
                preorder_position=self, type="redeem"
            ).last()
            tz = timezone.get_current_timezone()

            return _(
                "This ticket ({secret}…) has already been redeemed at {datetime}."
            ).format(
                datetime=last_r.transaction.datetime.astimezone(tz).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                secret=self.secret[:6],
            )
