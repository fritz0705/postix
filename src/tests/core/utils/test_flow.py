from decimal import Decimal

import pytest
from django.db.models import Sum
from tests.factories import (
    cashdesk_session_after_factory, cashdesk_session_before_factory,
    list_constraint_entry_factory, list_constraint_factory,
    preorder_position_factory, product_factory, time_constraint_factory,
    transaction_factory, transaction_position_factory, user_factory,
    warning_constraint_factory,
)

from postix.core.models import (
    ListConstraintProduct, Transaction, TransactionPosition,
    TransactionPositionItem, WarningConstraintProduct,
)
from postix.core.utils.checks import is_redeemed
from postix.core.utils.flow import (
    FlowError, redeem_preorder_ticket, reverse_session, reverse_transaction,
    reverse_transaction_position, sell_ticket,
)


@pytest.mark.django_db
def test_invalid():
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret='abcde')
    assert excinfo.value.message == 'No ticket could be found with the given secret.'


@pytest.mark.django_db
def test_canceled():
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=preorder_position_factory(canceled=True).secret)
    assert excinfo.value.message == 'This ticket has been canceled or is expired.'


@pytest.mark.django_db
def test_unpaid_no_price():
    pp = preorder_position_factory(paid=False, price=None)
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pp.secret)
    assert excinfo.value.message == 'This ticket has not been paid for.'
    assert excinfo.value.bypass_price is None


@pytest.mark.django_db
def test_unpaid_price():
    pp = preorder_position_factory(paid=False, price=23.0)
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pp.secret)
    assert excinfo.value.message == 'This ticket has not been paid for.'
    assert excinfo.value.bypass_price == Decimal('23.00')

    pos = redeem_preorder_ticket(secret=pp.secret, bypass_price=Decimal('23.00'))
    assert pos.value == Decimal('23.00')
    assert pos.tax_rate == Decimal('19.00')
    pos.transaction = transaction_factory()
    pos.save()
    assert pp.is_redeemed
    assert pos.transaction.value == Decimal('23.00')


@pytest.mark.django_db
def test_already_redeemed():
    pos = preorder_position_factory(paid=True, redeemed=True)
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pos.secret)
    assert 'already been redeemed' in excinfo.value.message
    assert 'already been redeemed at' in pos.redemption_message


@pytest.mark.django_db
def test_simple_valid():
    pp = preorder_position_factory(paid=True, redeemed=False)
    pos = redeem_preorder_ticket(secret=pp.secret)
    assert isinstance(pos, TransactionPosition)
    assert pos.value == Decimal('0.00')
    assert pos.product == pp.product
    pos.transaction = transaction_factory()
    pos.save()
    assert is_redeemed(pp)


@pytest.mark.django_db
def test_preorder_warning():
    pp = preorder_position_factory(paid=True)
    pp.preorder.warning_text = "Foo"
    pp.preorder.save()
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pp.secret)
    assert excinfo.value.message == 'Foo'
    assert excinfo.value.type == 'confirmation'
    assert excinfo.value.missing_field == 'warning_acknowledged'


@pytest.mark.django_db
def test_preorder_warning_constraint():
    pp = preorder_position_factory(paid=True)
    warning_constraint = warning_constraint_factory()
    WarningConstraintProduct.objects.create(
        product=pp.product, constraint=warning_constraint
    )
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pp.secret)
    assert excinfo.value.message == warning_constraint.message
    assert excinfo.value.type == 'confirmation'
    assert excinfo.value.missing_field == 'warning_{}_acknowledged'.format(
        warning_constraint.pk
    )


@pytest.mark.django_db
def test_preorder_warning_constraint_passed():
    pp = preorder_position_factory(paid=True)
    warning_constraint = warning_constraint_factory()
    WarningConstraintProduct.objects.create(
        product=pp.product, constraint=warning_constraint
    )
    options = {'warning_{}_acknowledged'.format(warning_constraint.pk): 'ok'}
    redeem_preorder_ticket(secret=pp.secret, **options)


@pytest.mark.django_db
def test_preorder_warning_constraint_bypass_to_low():
    pp = preorder_position_factory(paid=True)
    warning_constraint = warning_constraint_factory()
    WarningConstraintProduct.objects.create(
        product=pp.product, constraint=warning_constraint, price=Decimal('7.00')
    )
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pp.secret)
    assert excinfo.value.message == warning_constraint.message
    assert excinfo.value.type == 'confirmation'
    assert excinfo.value.missing_field == 'warning_{}_acknowledged'.format(
        warning_constraint.pk
    )
    with pytest.raises(FlowError):
        redeem_preorder_ticket(secret=pp.secret, bypass_price=4)


@pytest.mark.django_db
def test_preorder_time_constraint_inactive():
    pp = preorder_position_factory(paid=True)
    time_constraint = time_constraint_factory(active=False)
    time_constraint.products.add(pp.product)
    with pytest.raises(FlowError):
        redeem_preorder_ticket(secret=pp.secret)


@pytest.mark.django_db
def test_preorder_time_constraint_active():
    pp = preorder_position_factory(paid=True)
    time_constraint = time_constraint_factory(active=True)
    time_constraint.products.add(pp.product)
    redeem_preorder_ticket(secret=pp.secret)


@pytest.mark.django_db
def test_preorder_warning_constraint_bypass_price_paid():
    pp = preorder_position_factory(paid=True)
    warning_constraint = warning_constraint_factory()
    WarningConstraintProduct.objects.create(
        product=pp.product, constraint=warning_constraint, price=Decimal('7.00')
    )
    options = {'bypass_price': 7}
    pos = redeem_preorder_ticket(secret=pp.secret, **options)
    assert pos.value == Decimal('7.00')


@pytest.mark.django_db
def test_preorder_list_constraint_bypass_success():
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory(
        product=pp.product, price=Decimal('23.00')
    )
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pp.secret)
    assert (
        excinfo.value.message
        == 'This ticket can only redeemed by persons on the list "{}".'.format(
            list_constraint.name
        )
    )
    assert excinfo.value.type == 'input'
    assert excinfo.value.missing_field == 'list_{}'.format(list_constraint.pk)
    assert excinfo.value.bypass_price == Decimal('23.00')
    pos = redeem_preorder_ticket(secret=pp.secret, bypass_price=23.0)
    assert pos.value == Decimal('23.00')
    assert pos.tax_rate == Decimal('19.00')
    pos.transaction = transaction_factory()
    pos.save()
    assert pp.is_redeemed
    assert pos.transaction.value == Decimal('23.00')


@pytest.mark.django_db
def test_preorder_list_constraint_bypass_too_low():
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory(
        product=pp.product, price=Decimal('23.00')
    )
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pp.secret)
    assert (
        excinfo.value.message
        == 'This ticket can only redeemed by persons on the list "{}".'.format(
            list_constraint.name
        )
    )
    assert excinfo.value.type == 'input'
    assert excinfo.value.missing_field == 'list_{}'.format(list_constraint.pk)
    assert excinfo.value.bypass_price == Decimal('23.00')
    with pytest.raises(FlowError):
        redeem_preorder_ticket(secret=pp.secret, bypass_price=12.0)


@pytest.mark.django_db
def test_preorder_list_constraint():
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory()
    ListConstraintProduct.objects.create(product=pp.product, constraint=list_constraint)
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pp.secret)
    assert (
        excinfo.value.message
        == 'This ticket can only redeemed by persons on the list "{}".'.format(
            list_constraint.name
        )
    )
    assert excinfo.value.type == 'input'
    assert excinfo.value.missing_field == 'list_{}'.format(list_constraint.pk)


@pytest.mark.django_db
def test_preorder_list_constraint_unknown():
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory()
    ListConstraintProduct.objects.create(product=pp.product, constraint=list_constraint)
    options = {'list_{}'.format(list_constraint.pk): '2'}
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pp.secret, **options)
    assert (
        excinfo.value.message
        == 'This entry could not be found in list "{}".'.format(list_constraint.name)
    )
    assert excinfo.value.type == 'input'
    assert excinfo.value.missing_field == 'list_{}'.format(list_constraint.pk)


@pytest.mark.django_db
def test_preorder_list_constraint_used():
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory()
    entry = list_constraint_entry_factory(
        list_constraint=list_constraint, redeemed=True
    )
    ListConstraintProduct.objects.create(product=pp.product, constraint=entry.list)
    options = {'list_{}'.format(entry.list.pk): str(entry.identifier)}
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pp.secret, **options)
    assert excinfo.value.message == 'This list entry has already been used.'
    assert excinfo.value.type == 'input'
    assert excinfo.value.missing_field == 'list_{}'.format(list_constraint.pk)


@pytest.mark.django_db
def test_preorder_list_constraint_success():
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory()
    entry = list_constraint_entry_factory(
        list_constraint=list_constraint, redeemed=False
    )
    ListConstraintProduct.objects.create(product=pp.product, constraint=entry.list)
    options = {'list_{}'.format(entry.list.pk): str(entry.identifier)}
    pos = redeem_preorder_ticket(secret=pp.secret, **options)
    assert pos.listentry == entry


@pytest.mark.django_db
def test_preorder_list_constraint_troubleshooter_bypass():
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory()
    ListConstraintProduct.objects.create(product=pp.product, constraint=list_constraint)
    user = user_factory(troubleshooter=True)
    user.auth_token = 'abcdefg'
    user.save()
    options = {'list_{}'.format(list_constraint.pk): str(user.auth_token)}
    pos = redeem_preorder_ticket(secret=pp.secret, **options)
    assert pos.listentry is None
    assert pos.authorized_by == user


@pytest.mark.django_db
def test_preorder_list_and_warning_bypass():
    pp = preorder_position_factory(paid=True)
    warning_constraint = warning_constraint_factory()
    WarningConstraintProduct.objects.create(
        product=pp.product, constraint=warning_constraint, price=Decimal('23.00')
    )
    list_constraint = list_constraint_factory()
    ListConstraintProduct.objects.create(
        product=pp.product, constraint=list_constraint, price=Decimal('12.00')
    )
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pp.secret)
    assert excinfo.value.bypass_price == Decimal('23.00')

    options = {'bypass_price': '23.00'}
    with pytest.raises(FlowError) as excinfo:
        redeem_preorder_ticket(secret=pp.secret, **options)
    assert (
        excinfo.value.message
        == 'This ticket can only redeemed by persons on the list "{}".'.format(
            list_constraint.name
        )
    )
    assert excinfo.value.type == 'input'
    assert excinfo.value.missing_field == 'list_{}'.format(list_constraint.pk)
    assert excinfo.value.bypass_price == Decimal('12.00')

    pos = redeem_preorder_ticket(secret=pp.secret, bypass_price=35.0)
    assert pos.value == Decimal('35.00')


@pytest.mark.django_db
def test_sell_unknown_product():
    with pytest.raises(FlowError) as excinfo:
        sell_ticket(product=1234678)
    assert excinfo.value.message == 'This product ID is not known.'


@pytest.mark.django_db
def test_sell_unavailable_product():
    p = product_factory()
    t = time_constraint_factory(active=False)
    t.products.add(p)
    with pytest.raises(FlowError) as excinfo:
        sell_ticket(product=p.pk)
    assert excinfo.value.message == 'This product is currently unavailable or sold out.'


@pytest.mark.django_db
def test_sell_warning_constraint():
    p = product_factory()
    warning_constraint = warning_constraint_factory()
    WarningConstraintProduct.objects.create(product=p, constraint=warning_constraint)
    with pytest.raises(FlowError) as excinfo:
        sell_ticket(product=p.pk)
    assert excinfo.value.message == warning_constraint.message
    assert excinfo.value.type == 'confirmation'
    assert excinfo.value.missing_field == 'warning_{}_acknowledged'.format(
        warning_constraint.pk
    )


@pytest.mark.django_db
def test_sell_warning_constraint_passed():
    p = product_factory()
    warning_constraint = warning_constraint_factory()
    WarningConstraintProduct.objects.create(product=p, constraint=warning_constraint)
    options = {'warning_{}_acknowledged'.format(warning_constraint.pk): 'ok'}
    sell_ticket(product=p.id, **options)


@pytest.mark.django_db
def test_sell_list_constraint():
    p = product_factory()
    list_constraint = list_constraint_factory()
    ListConstraintProduct.objects.create(product=p, constraint=list_constraint)
    with pytest.raises(FlowError) as excinfo:
        sell_ticket(product=p.id)
    assert (
        excinfo.value.message
        == 'This ticket can only redeemed by persons on the list "{}".'.format(
            list_constraint.name
        )
    )
    assert excinfo.value.type == 'input'
    assert excinfo.value.missing_field == 'list_{}'.format(list_constraint.pk)


@pytest.mark.django_db
def test_sell_list_constraint_unknown():
    p = product_factory()
    list_constraint = list_constraint_factory()
    ListConstraintProduct.objects.create(product=p, constraint=list_constraint)
    options = {'list_{}'.format(list_constraint.pk): '2'}
    with pytest.raises(FlowError) as excinfo:
        sell_ticket(product=p.id, **options)
    assert (
        excinfo.value.message
        == 'This entry could not be found in list "{}".'.format(list_constraint.name)
    )
    assert excinfo.value.type == 'input'
    assert excinfo.value.missing_field == 'list_{}'.format(list_constraint.pk)


@pytest.mark.django_db
def test_sell_list_constraint_used():
    p = product_factory()
    list_constraint = list_constraint_factory()
    entry = list_constraint_entry_factory(
        list_constraint=list_constraint, redeemed=True
    )
    ListConstraintProduct.objects.create(product=p, constraint=entry.list)
    options = {'list_{}'.format(entry.list.pk): str(entry.identifier)}
    with pytest.raises(FlowError) as excinfo:
        sell_ticket(product=p.id, **options)
    assert excinfo.value.message == 'This list entry has already been used.'
    assert excinfo.value.type == 'input'
    assert excinfo.value.missing_field == 'list_{}'.format(list_constraint.pk)


@pytest.mark.django_db
def test_sell_list_constraint_success():
    p = product_factory()
    list_constraint = list_constraint_factory()
    entry = list_constraint_entry_factory(
        list_constraint=list_constraint, redeemed=False
    )
    ListConstraintProduct.objects.create(product=p, constraint=entry.list)
    options = {'list_{}'.format(entry.list.pk): str(entry.identifier)}
    pos = sell_ticket(product=p.id, **options)
    assert pos.listentry == entry


@pytest.mark.django_db
def test_sell_list_constraint_troubleshooter_bypass():
    p = product_factory()
    list_constraint = list_constraint_factory()
    ListConstraintProduct.objects.create(product=p, constraint=list_constraint)
    user = user_factory(troubleshooter=True)
    user.auth_token = 'abcdefg'
    user.save()
    options = {'list_{}'.format(list_constraint.pk): str(user.auth_token)}
    pos = sell_ticket(product=p.id, **options)
    assert pos.listentry is None
    assert pos.authorized_by == user


@pytest.mark.django_db
def test_reverse_unknown():
    session = cashdesk_session_before_factory()
    with pytest.raises(FlowError) as excinfo:
        reverse_transaction(trans_id=1234678, current_session=session)
    assert excinfo.value.message == 'Transaction ID not known.'


@pytest.mark.django_db
def test_reverse_wrong_session():
    session1 = cashdesk_session_before_factory()
    session2 = cashdesk_session_before_factory()
    trans = transaction_factory(session1)
    transaction_position_factory(transaction=trans)
    with pytest.raises(FlowError) as excinfo:
        reverse_transaction(trans_id=trans.pk, current_session=session2)
    assert (
        excinfo.value.message
        == 'Only troubleshooters can reverse sales from other sessions.'
    )


@pytest.mark.django_db
def test_reverse_wrong_session_troubleshooter():
    session1 = cashdesk_session_before_factory()
    session2 = cashdesk_session_before_factory(user=user_factory(troubleshooter=True))
    trans = transaction_factory(session1)
    transaction_position_factory(transaction=trans)
    reverse_transaction(
        trans_id=trans.pk,
        current_session=session2,
        authorized_by=user_factory(troubleshooter=True),
    )


@pytest.mark.django_db
def test_reverse_success():
    session = cashdesk_session_before_factory()
    trans = transaction_factory(session)
    pos = [
        transaction_position_factory(
            transaction=trans, product=product_factory(items=True)
        ),
        transaction_position_factory(transaction=trans),
    ]
    revtransid = reverse_transaction(trans_id=trans.pk, current_session=session)
    revtrans = Transaction.objects.get(pk=revtransid)
    assert revtrans.session == session
    revpos = revtrans.positions.all()
    assert len(revpos) == len(pos)
    for lp, rp in zip(pos, revpos):
        assert rp.reverses == lp
        assert rp.type == 'reverse'
        assert rp.value == -1 * lp.value
        assert rp.tax_value == -1 * lp.tax_value
        assert rp.product == lp.product
        assert {i.id for i in lp.items.all()} == {i.id for i in rp.items.all()}

        ls = TransactionPositionItem.objects.filter(position=lp).aggregate(
            s=Sum('amount')
        )['s']
        if ls:
            rs = TransactionPositionItem.objects.filter(position=rp).aggregate(
                s=Sum('amount')
            )['s']
            assert rs == ls * -1


@pytest.mark.django_db
def test_reverse_double():
    session = cashdesk_session_before_factory()
    trans = transaction_factory(session)
    transaction_position_factory(transaction=trans, product=product_factory(items=True))
    transaction_position_factory(transaction=trans)
    reverse_transaction(trans_id=trans.pk, current_session=session)
    with pytest.raises(FlowError) as excinfo:
        reverse_transaction(trans_id=trans.pk, current_session=session)
    assert (
        excinfo.value.message
        == 'At least one position of this transaction has already been reversed.'
    )


@pytest.mark.django_db
def test_reverse_reversal():
    session = cashdesk_session_before_factory()
    trans = transaction_factory(session)
    transaction_position_factory(transaction=trans, product=product_factory(items=True))
    transaction_position_factory(transaction=trans)
    trans = reverse_transaction(trans_id=trans.pk, current_session=session)
    with pytest.raises(FlowError) as excinfo:
        reverse_transaction(trans_id=trans, current_session=session)
    assert (
        excinfo.value.message
        == 'At least one position of this transaction is a reversal.'
    )


@pytest.mark.django_db
def test_reverse_position_unknown():
    session = cashdesk_session_before_factory()
    with pytest.raises(FlowError) as excinfo:
        reverse_transaction_position(1234678, current_session=session)
    assert excinfo.value.message == 'Transaction position ID not known.'


@pytest.mark.django_db
def test_reverse_position_wrong_session():
    session1 = cashdesk_session_before_factory()
    session2 = cashdesk_session_before_factory()
    trans = transaction_factory(session1)
    tpos = transaction_position_factory(transaction=trans)
    with pytest.raises(FlowError) as excinfo:
        reverse_transaction_position(tpos.pk, current_session=session2)
    assert (
        excinfo.value.message
        == 'Only troubleshooters can reverse sales from other sessions.'
    )


@pytest.mark.django_db
def test_reverse_position_wrong_session_troubleshooter():
    session1 = cashdesk_session_before_factory()
    session2 = cashdesk_session_before_factory(user=user_factory(troubleshooter=True))
    trans = transaction_factory(session1)
    tpos = transaction_position_factory(transaction=trans)
    reverse_transaction_position(
        tpos.pk,
        current_session=session2,
        authorized_by=user_factory(troubleshooter=True),
    )


@pytest.mark.django_db
def test_reverse_success_single():
    session = cashdesk_session_before_factory()
    trans = transaction_factory(session)
    lp = transaction_position_factory(
        transaction=trans, product=product_factory(items=True)
    )
    revtrans = Transaction.objects.get(
        pk=reverse_transaction_position(trans_pos_id=lp.pk, current_session=session)
    )
    assert revtrans.session == session
    revpos = revtrans.positions.all()
    assert len(revpos) == 1
    rp = revpos[0]

    assert rp.reverses == lp
    assert rp.type == 'reverse'
    assert rp.value == -1 * lp.value
    assert rp.tax_value == -1 * lp.tax_value
    assert rp.product == lp.product
    assert {i.id for i in lp.items.all()} == {i.id for i in rp.items.all()}

    ls = TransactionPositionItem.objects.filter(position=lp).aggregate(s=Sum('amount'))[
        's'
    ]
    if ls:
        rs = TransactionPositionItem.objects.filter(position=rp).aggregate(
            s=Sum('amount')
        )['s']
        assert rs == ls * -1


@pytest.mark.django_db
def test_reverse_position_double():
    session = cashdesk_session_before_factory()
    trans = transaction_factory(session)
    tpos = transaction_position_factory(
        transaction=trans, product=product_factory(items=True)
    )
    reverse_transaction_position(tpos.pk, current_session=session)
    with pytest.raises(FlowError) as excinfo:
        reverse_transaction_position(tpos.pk, current_session=session)
    assert excinfo.value.message == 'This position has already been reversed.'


@pytest.mark.django_db
def test_reverse_position_reversal():
    session = cashdesk_session_before_factory()
    trans = transaction_factory(session)
    tpos = transaction_position_factory(
        transaction=trans, product=product_factory(items=True)
    )
    pos = reverse_transaction_position(tpos.pk, current_session=session)
    with pytest.raises(FlowError) as excinfo:
        reverse_transaction_position(pos, current_session=session)
    assert excinfo.value.message == 'This position is already a reversal.'


@pytest.mark.django_db
def test_reverse_whole_session_double():
    session = cashdesk_session_before_factory()
    pp = preorder_position_factory(paid=True)
    trans = transaction_factory(session)
    transaction_position_factory(transaction=trans, product=product_factory(items=True))
    pos = redeem_preorder_ticket(secret=pp.secret)
    pos.transaction = trans
    pos.save()
    assert is_redeemed(pp)
    reverse_session(session)
    with pytest.raises(FlowError):
        reverse_session(session)


@pytest.mark.django_db
def test_reverse_whole_session_inactive():
    session = cashdesk_session_after_factory()
    pp = preorder_position_factory(paid=True)
    trans = transaction_factory(session)
    transaction_position_factory(transaction=trans, product=product_factory(items=True))
    pos = redeem_preorder_ticket(secret=pp.secret)
    pos.transaction = trans
    pos.save()
    assert is_redeemed(pp)
    with pytest.raises(FlowError) as excinfo:
        reverse_session(session)
    assert excinfo.value.message == 'The session needs to be still active.'


@pytest.mark.django_db
def test_reverse_whole_session():
    session = cashdesk_session_before_factory()
    pp = preorder_position_factory(paid=True)
    trans = transaction_factory(session)
    transaction_position_factory(transaction=trans, product=product_factory(items=True))
    pos = redeem_preorder_ticket(secret=pp.secret)
    pos.transaction = trans
    pos.save()
    assert is_redeemed(pp)
    reverse_session(session)
    assert not is_redeemed(pp)
