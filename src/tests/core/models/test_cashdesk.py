from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils.timezone import now
from tests.factories import (
    cashdesk_session_before_factory,
    transaction_factory,
    transaction_position_factory,
    user_factory,
)

from postix.core.models import (
    Item,
    ItemMovement,
    Product,
    ProductItem,
    TransactionPosition,
)
from postix.core.utils import times
from postix.core.utils.flow import reverse_transaction


@pytest.mark.django_db
def test_session_active():
    session = cashdesk_session_before_factory()
    assert session.is_active()


@pytest.mark.django_db
def test_session_not_active():
    session = cashdesk_session_before_factory()
    session.end = now() - timedelta(hours=1)
    assert not session.is_active()


@pytest.mark.django_db
def test_cashdesk_device_actions():
    desk = cashdesk_session_before_factory(create_items=False).cashdesk
    desk.signal_open()
    desk.signal_next()
    desk.signal_close()
    assert "Dummy" in str(desk.printer)
    desk.printer_queue_name = "printer1"
    assert "Dummy" not in str(desk.printer)


@pytest.mark.django_db
def test_current_items():
    session = cashdesk_session_before_factory(create_items=False)
    buser = user_factory(troubleshooter=True, superuser=True)
    item_full = Item.objects.create(name="Full pass", description="", initial_stock=200)
    item_1d = Item.objects.create(
        name="One day pass", description="", initial_stock=100
    )
    prod_full = Product.objects.create(name="Full ticket", price=23, tax_rate=19)
    prod_1d = Product.objects.create(name="One day ticket", price=12, tax_rate=19)
    ProductItem.objects.create(product=prod_full, item=item_full, amount=1)
    ProductItem.objects.create(product=prod_1d, item=item_1d, amount=1)
    ItemMovement.objects.create(
        session=session, item=item_full, amount=20, backoffice_user=buser
    )
    ItemMovement.objects.create(
        session=session, item=item_1d, amount=10, backoffice_user=buser
    )
    assert session.cash_remaining == session.cash_before
    assert session.is_latest_session

    for _ in times(3):
        transaction_position_factory(transaction_factory(session), prod_full)
    for _ in times(2):
        transaction_position_factory(transaction_factory(session), prod_1d)

    trans = transaction_position_factory(
        transaction_factory(session), prod_1d
    ).transaction
    reverse_transaction(trans_id=trans.pk, current_session=session)

    session.end = now()
    session.save()
    ItemMovement.objects.create(
        session=session, item=item_full, amount=-17, backoffice_user=buser
    )
    ItemMovement.objects.create(
        session=session, item=item_1d, amount=-5, backoffice_user=buser
    )

    assert session.get_current_items() == [
        {
            "movements": 20,
            "total": 0,
            "transactions": 3,
            "item": item_full,
            "final_movements": 17,
        },
        {
            "movements": 10,
            "total": 3,
            "transactions": 2,
            "item": item_1d,
            "final_movements": 5,
        },
    ]


@pytest.mark.django_db
def test_cash_transaction_total():
    session = cashdesk_session_before_factory(create_items=False)
    prod_full = Product.objects.create(name="Full ticket", price=23, tax_rate=19)

    for _ in times(3):
        transaction_position_factory(transaction_factory(session), prod_full)
    trans = transaction_position_factory(
        transaction_factory(session), prod_full
    ).transaction
    reverse_transaction(trans_id=trans.pk, current_session=session)

    TransactionPosition.objects.create(
        type="redeem",
        value=10,
        tax_rate=19,
        product=prod_full,
        transaction=transaction_factory(session),
        has_constraint_bypass=True,
    )

    assert session.get_cash_transaction_total() == 23 * 3 + 10


@pytest.mark.django_db
def test_product_sales():
    session = cashdesk_session_before_factory(create_items=False)
    prod_full = Product.objects.create(name="Full ticket", price=23, tax_rate=19)

    for _ in times(3):
        transaction_position_factory(transaction_factory(session), prod_full)
    trans = transaction_position_factory(transaction_factory(session), prod_full)
    reverse_transaction(trans_id=trans.transaction_id, current_session=session)

    TransactionPosition.objects.create(
        type="redeem",
        value=10,
        tax_rate=19,
        product=prod_full,
        transaction=transaction_factory(session),
        has_constraint_bypass=True,
    )
    TransactionPosition.objects.create(
        type="redeem",
        value=0,
        tax_rate=0,
        product=prod_full,
        transaction=transaction_factory(session),
    )

    def keyfunc(d):
        return d["value_single"]

    assert sorted(session.get_product_sales(), key=keyfunc) == sorted(
        [
            {
                "product": prod_full,
                "presales": 0,
                "reversals": 1,
                "sales": 4,
                "value_total": Decimal("69.00"),
                "value_single": Decimal("23.00"),
            },
            {
                "product": prod_full,
                "presales": 1,
                "reversals": 0,
                "sales": 0,
                "value_total": Decimal("00.00"),
                "value_single": Decimal("00.00"),
            },
            {
                "product": prod_full,
                "presales": 1,
                "reversals": 0,
                "sales": 0,
                "value_total": Decimal("10.00"),
                "value_single": Decimal("10.00"),
            },
        ],
        key=keyfunc,
    )
