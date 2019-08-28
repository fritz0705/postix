import json

import pytest

from ..factories import itemsupplypack_factory, ping_factory, transaction_factory


@pytest.mark.django_db
def test_open_drawer(api_with_session):
    response = api_with_session.post("/api/cashdesk/open-drawer/")
    content = json.loads(response.content.decode())
    assert content == {"success": True}


@pytest.mark.django_db
def test_reprint_receipt(api_with_session):
    transaction = transaction_factory()
    response = api_with_session.post(
        "/api/cashdesk/reprint-receipt/", {"transaction": transaction.id}
    )
    content = json.loads(response.content.decode())
    assert content == {"success": True}


@pytest.mark.django_db
def test_reprint_receipt_fail(api_with_session):
    transaction = transaction_factory()
    response = api_with_session.post(
        "/api/cashdesk/reprint-receipt/", {"transaction": transaction.id + 1337}
    )
    content = json.loads(response.content.decode())
    assert content == {"success": False, "error": "Transaction not found."}


@pytest.mark.django_db
def test_signal_next(api_with_session):
    response = api_with_session.post("/api/cashdesk/signal-next/")
    content = json.loads(response.content.decode())
    assert content == {"success": True}


@pytest.mark.django_db
def test_print_ping(api_with_session):
    response = api_with_session.post("/api/cashdesk/print-ping/")
    content = json.loads(response.content.decode())
    assert content == {"success": True}


@pytest.mark.django_db
def test_pong_ping(api_with_session):
    p = ping_factory()
    response = api_with_session.post("/api/cashdesk/pong/", {"pong": p.secret})
    content = json.loads(response.content.decode())
    assert content == {"success": True}
    p.refresh_from_db()
    assert p.ponged


@pytest.mark.django_db
def test_pong_ping_broken_code(api_with_session):
    p = ping_factory()
    response = api_with_session.post(
        "/api/cashdesk/pong/", {"pong": p.secret + "lolol"}
    )
    content = json.loads(response.content.decode())
    assert content == {"success": True}
    p.refresh_from_db()
    assert not p.ponged


@pytest.mark.django_db
def test_request_resupply(api_with_session):
    response = api_with_session.post("/api/cashdesk/request-resupply/")
    content = json.loads(response.content.decode())
    assert content == {"success": True}


@pytest.mark.django_db
def test_supply_invalid_identifier(api_with_session, session):
    response = api_with_session.post("/api/cashdesk/supply/", {"identifier": "foo"})
    content = json.loads(response.content.decode())
    assert not content["success"]


@pytest.mark.django_db
def test_supply_invalid_state(api_with_session, session):
    p = itemsupplypack_factory(state="backoffice")
    response = api_with_session.post(
        "/api/cashdesk/supply/", {"identifier": p.identifier}
    )
    content = json.loads(response.content.decode())
    assert not content["success"]


@pytest.mark.django_db
def test_supply_valid(api_with_session, session):
    p = itemsupplypack_factory(state="troubleshooter")
    response = api_with_session.post(
        "/api/cashdesk/supply/", {"identifier": p.identifier}
    )
    content = json.loads(response.content.decode())
    assert content["success"]
    p.refresh_from_db()
    assert p.state == "used"
    pl = p.logs.last()
    assert pl.user == session.user
    assert pl.new_state == "used"
    im = pl.item_movement
    assert im.backoffice_user == session.user
    assert im.item == p.item
    assert im.amount == p.amount
