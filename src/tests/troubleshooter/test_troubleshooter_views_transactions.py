import pytest

from ..factories import (
    cashdesk_factory,
    transaction_factory,
    transaction_position_factory,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    (
        {"type": "redeem"},
        {"type": "redeeem"},
        {"desk": 1},
        {"desk": 100},
        {"receipt": 1},
        {"receipt": "lala"},
    ),
)
def test_troubleshooter_can_see_and_filter_transactions(troubleshooter_client, query):
    query_string = "?{}={}".format(list(query.keys())[0], list(query.values())[0])
    cashdesk_factory()
    transaction_factory()
    transaction_position_factory()
    response = troubleshooter_client.get("/troubleshooter/transactions/" + query_string)
    assert response.status_code == 200


@pytest.mark.django_db
def test_troubleshooter_can_see_single_transactions(troubleshooter_client):
    tr = transaction_factory()
    response = troubleshooter_client.get(
        "/troubleshooter/transactions/{}/".format(tr.pk)
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_troubleshooter_can_reprint_receipt(troubleshooter_client):
    tr = transaction_position_factory()
    response = troubleshooter_client.post(
        "/troubleshooter/transactions/{}/reprint/".format(tr.transaction.pk),
        follow=True,
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_troubleshooter_can_generate_invoice(troubleshooter_client, event_settings):
    tr = transaction_position_factory()
    response = troubleshooter_client.post(
        "/troubleshooter/transactions/{}/invoice/".format(tr.transaction.pk),
        {"address": "An address"},
        follow=True,
    )
    assert response.status_code == 200
