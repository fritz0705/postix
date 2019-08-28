import copy
from decimal import Decimal

from django.utils import timezone
from django.utils.translation import ugettext as _

from ..models import (
    CashdeskSession,
    ListConstraintEntry,
    ListConstraintProduct,
    PreorderPosition,
    Product,
    Transaction,
    TransactionPosition,
    TransactionPositionItem,
    User,
)
from .checks import is_redeemed


class FlowError(Exception):
    def __init__(
        self,
        msg: str,
        type: str = "error",
        missing_field: str = None,
        bypass_price: Decimal = None,
    ) -> None:
        self.message = msg
        self.type = type
        self.missing_field = missing_field
        self.bypass_price = bypass_price

    def __str__(self) -> str:
        return self.message


def redeem_preorder_ticket(**kwargs) -> TransactionPosition:
    """
    Creates a TransactionPosition object that validates a given preorder position.
    This checks the various constraints placed on the given position and item and
    raises a FlowError if one of the conditions can't be met. This FlowError will
    contain information which additional keyword arguments you need to provide to
    fulfull the conditions (if possible).

    :param secret: The secret of the preorder position (i.e. the scanned barcode)
    :returns: The TransactionPosition object
    """
    pos = TransactionPosition(type="redeem")
    bypass_price = bypass_price_paying = Decimal(kwargs.get("bypass_price", "0.00"))
    bypass_taxrate = None

    if "secret" not in kwargs:  # noqa
        raise FlowError(_("No secret has been given."))

    try:
        # To prevent double redemptions of a preorder, we need to play around with
        # database locking here. SELECT FOR UPDATE alone does not help here, as we
        # do not actually update the PreorderPosition object. Therefore, we use the
        # transaction ID as a flag that we actually update.
        # In the scenario that a different transaction runs concurrently with this and
        # tries to redeem this ticket, both will get the same last_trans_id but the
        # second transactions blocks at the select_for_update call until the first one
        # is finished. Once the lock is released, it continues -- but with the updated
        # PreorderPosition that now has a different last_transaction. In this case,
        # we fail loudly.
        trans_id = kwargs.get("transaction_id", None)
        pp = PreorderPosition.objects.get(secret=kwargs.get("secret"))
        last_trans_id = pp.last_transaction

        pp = PreorderPosition.objects.select_for_update().get(
            secret=kwargs.get("secret")
        )
        if pp.last_transaction != last_trans_id:
            raise FlowError(_("Race condition. Please try again."))

        pp.last_transaction = trans_id
        pp.save()
    except PreorderPosition.DoesNotExist:
        raise FlowError(_("No ticket could be found with the given secret."))

    if pp.preorder.is_canceled:
        raise FlowError(_("This ticket has been canceled or is expired."))

    if not pp.preorder.is_paid:
        if pp.price is not None and bypass_price_paying >= pp.price:
            bypass_price_paying -= pp.price
            bypass_taxrate = pp.product.tax_rate
        else:
            raise FlowError(
                _("This ticket has not been paid for."),
                type="confirmation",
                missing_field="pay_for_unpaid",
                bypass_price=pp.price,
            )

    if not pp.product.is_availably_by_time:
        raise FlowError(_("This product is currently not available."))

    if is_redeemed(pp):
        last_r = TransactionPosition.objects.filter(
            preorder_position=pp, type="redeem"
        ).last()
        tz = timezone.get_current_timezone()

        raise FlowError(
            _(
                "This ticket ({secret}…) has already been redeemed at {datetime}."
            ).format(
                datetime=last_r.transaction.datetime.astimezone(tz).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                secret=pp.secret[:6],
            )
        )

    if pp.preorder.warning_text and "warning_acknowledged" not in kwargs:
        raise FlowError(
            pp.preorder.warning_text,
            type="confirmation",
            missing_field="warning_acknowledged",
        )

    for c in pp.product.product_warning_constraints.all():
        if "warning_{}_acknowledged".format(c.constraint.pk) not in kwargs:
            if c.price is not None and bypass_price_paying >= c.price:
                bypass_price_paying -= c.price
                bypass_taxrate = c.tax_rate
            else:
                raise FlowError(
                    c.constraint.message,
                    type="confirmation",
                    missing_field="warning_{}_acknowledged".format(c.constraint.pk),
                    bypass_price=c.price,
                )

    try:
        c = pp.product.product_list_constraint
        entryid = kwargs.get("list_{}".format(c.constraint.pk), None)
        if c.price is not None and bypass_price_paying >= c.price:
            bypass_price_paying -= c.price
            if bypass_taxrate is not None and bypass_taxrate != c.tax_rate:
                raise FlowError(
                    _("Multiple upgrades with different tax rates are not supported.")
                )
            bypass_taxrate = c.tax_rate
        else:
            if not entryid:
                raise FlowError(
                    _(
                        'This ticket can only redeemed by persons on the list "{}".'
                    ).format(c.constraint.name),
                    type="input",
                    missing_field="list_{}".format(c.constraint.pk),
                    bypass_price=c.price,
                )
            try:
                pos.authorized_by = User.objects.get(
                    is_troubleshooter=True, auth_token=entryid
                )
            except User.DoesNotExist:
                try:
                    entry = c.constraint.entries.get(identifier=entryid)
                    if is_redeemed(entry):
                        raise FlowError(
                            _("This list entry has already been used."),
                            type="input",
                            missing_field="list_{}".format(c.constraint.pk),
                            bypass_price=c.price,
                        )
                    else:
                        pos.listentry = entry
                except ListConstraintEntry.DoesNotExist:
                    raise FlowError(
                        _('This entry could not be found in list "{}".').format(
                            c.constraint.name
                        ),
                        type="input",
                        missing_field="list_{}".format(c.constraint.pk),
                        bypass_price=c.price,
                    )

    except ListConstraintProduct.DoesNotExist:
        pass

    pos.product = pp.product
    pos.preorder_position = pp
    if bypass_taxrate is not None and bypass_price:
        pos.value = bypass_price
        pos.tax_rate = bypass_taxrate  # tax_value is calculated by .save()
        pos.has_constraint_bypass = True
    else:
        pos.value = pos.tax_rate = Decimal("0.00")
    return pos


def sell_ticket(**kwargs) -> TransactionPosition:
    """
    Creates a TransactionPosition object that sells a given product.
    This checks the various constraints placed on the given product and item and
    raises a FlowError if one of the conditions can't be met. This FlowError will
    contain information which additional keyword arguments you need to provide to
    fulfull the conditions (if possible).

    :param product: The ID of the product to sell.
    :returns: The TransactionPosition object
    """
    pos = TransactionPosition(type="sell")

    if "product" not in kwargs:  # noqa
        raise FlowError(_("No product given."))

    try:
        product = Product.objects.get(id=kwargs.get("product"))
    except Product.DoesNotExist:
        raise FlowError(_("This product ID is not known."))

    if not product.is_available:
        auth = kwargs.get("auth", "!invalid")
        try:
            pos.authorized_by = User.objects.get(
                is_troubleshooter=True, auth_token=auth
            )
        except User.DoesNotExist:
            raise FlowError(
                _("This product is currently unavailable or sold out."),
                type="input",
                missing_field="auth",
            )

    if product.requires_authorization:
        auth = kwargs.get("auth", "!invalid")
        try:
            pos.authorized_by = User.objects.get(
                is_troubleshooter=True, auth_token=auth
            )
        except User.DoesNotExist:
            raise FlowError(
                _("This sale requires authorization by a troubleshooter."),
                type="input",
                missing_field="auth",
            )

    for c in product.product_warning_constraints.all():
        if "warning_{}_acknowledged".format(c.constraint.pk) not in kwargs:
            raise FlowError(
                c.constraint.message,
                type="confirmation",
                missing_field="warning_{}_acknowledged".format(c.constraint.pk),
            )

    try:
        c = product.product_list_constraint
        entryid = kwargs.get("list_{}".format(c.constraint.pk), None)
        if not entryid:
            raise FlowError(
                _('This ticket can only redeemed by persons on the list "{}".').format(
                    c.constraint.name
                ),
                type="input",
                missing_field="list_{}".format(c.constraint.pk),
            )
        try:
            pos.authorized_by = User.objects.get(
                is_troubleshooter=True, auth_token=entryid
            )
        except User.DoesNotExist:
            try:
                entry = c.constraint.entries.get(identifier=entryid)
                if is_redeemed(entry):
                    raise FlowError(
                        _("This list entry has already been used."),
                        type="input",
                        missing_field="list_{}".format(c.constraint.pk),
                    )
                else:
                    pos.listentry = entry
            except ListConstraintEntry.DoesNotExist:
                raise FlowError(
                    _('This entry could not be found in list "{}".').format(
                        c.constraint.name
                    ),
                    type="input",
                    missing_field="list_{}".format(c.constraint.pk),
                )
    except ListConstraintProduct.DoesNotExist:
        pass

    pos.product = product  # value, tax_* and items will be set automatically on save()
    return pos


def reverse_transaction(
    trans_id: int, current_session: CashdeskSession, authorized_by=None
) -> int:
    """
    Creates a Transaction that reverses an earlier transaction as a whole.

    :param trans_id: The ID of the transaction to reverse
    :returns: The new Transaction object
    """
    try:
        old_transaction = Transaction.objects.get(id=trans_id)
    except Transaction.DoesNotExist:
        raise FlowError(_("Transaction ID not known."))

    if not current_session.is_active():  # noqa (caught by auth layer)
        raise FlowError(_("You need to provide an active session."))

    if old_transaction.session != current_session:
        if not current_session.user.is_troubleshooter:
            if not authorized_by or not authorized_by.is_troubleshooter:
                raise FlowError(
                    _("Only troubleshooters can reverse sales from other sessions.")
                )

    if old_transaction.has_reversed_positions:
        raise FlowError(
            _("At least one position of this transaction has already been reversed.")
        )
    if old_transaction.has_reversals:
        raise FlowError(_("At least one position of this transaction is a reversal."))

    new_transaction = Transaction.objects.create(session=current_session)
    for old_pos in old_transaction.positions.all():
        new_pos = copy.copy(old_pos)
        new_pos.transaction = new_transaction
        new_pos.pk = None
        new_pos.type = "reverse"
        new_pos.value *= -1
        new_pos.tax_value *= -1
        new_pos.reverses = old_pos
        new_pos.authorized_by = None
        new_pos.save()
        for ip in TransactionPositionItem.objects.filter(position=new_pos):
            ip.amount *= -1
            ip.save()

    return new_transaction.pk


def reverse_transaction_position(
    trans_pos_id: int, current_session: CashdeskSession, authorized_by=None
) -> int:
    """
    Creates a Transaction that reverses a single transaction position.

    :param trans_pos_id: The ID of the transaction position to reverse
    :returns: The new Transaction object
    """
    try:
        old_pos = TransactionPosition.objects.get(id=trans_pos_id)
    except TransactionPosition.DoesNotExist:
        raise FlowError(_("Transaction position ID not known."))

    if not current_session.is_active():  # noqa (caught by auth layer)
        raise FlowError(_("You need to provide an active session."))

    if old_pos.transaction.session != current_session:
        if not current_session.user.is_troubleshooter:
            if not authorized_by or not authorized_by.is_troubleshooter:
                raise FlowError(
                    _("Only troubleshooters can reverse sales from other sessions.")
                )

    if old_pos.reversed_by.exists():
        raise FlowError(_("This position has already been reversed."))
    if old_pos.type == "reverse":
        raise FlowError(_("This position is already a reversal."))

    new_transaction = Transaction(session=current_session)
    new_transaction.save()
    new_pos = copy.copy(old_pos)
    new_pos.transaction = new_transaction
    new_pos.pk = None
    new_pos.type = "reverse"
    new_pos.value *= -1
    new_pos.tax_value *= -1
    new_pos.reverses = old_pos
    new_pos.authorized_by = None
    new_pos.save()
    for ip in TransactionPositionItem.objects.filter(position=new_pos):
        ip.amount *= -1
        ip.save()

    return new_transaction.pk


def reverse_session(session: CashdeskSession) -> int:
    """
    Creates a Transaction that reverses all earlier transactions of this
    session.

    :param session: The session to reverse
    :returns: The new Transaction object
    """
    if not session.is_active():
        raise FlowError(_("The session needs to be still active."))

    if TransactionPosition.objects.filter(
        transaction__session=session, type="reverse"
    ).exists():
        raise FlowError(
            _("For safety, you cannot execute this on sessions that contain reversals.")
        )

    new_transaction = Transaction(session=session)
    new_transaction.save()
    for old_pos in TransactionPosition.objects.filter(transaction__session=session):
        new_pos = copy.copy(old_pos)
        new_pos.transaction = new_transaction
        new_pos.pk = None
        new_pos.type = "reverse"
        new_pos.value *= -1
        new_pos.tax_value *= -1
        new_pos.reverses = old_pos
        new_pos.authorized_by = None
        new_pos.save()
        for ip in TransactionPositionItem.objects.filter(position=new_pos):
            ip.amount *= -1
            ip.save()

    return new_transaction.pk
