import pytest

from postix.core.models import CashdeskSession

from ..factories import (
    cashdesk_factory,
    cashdesk_session_after_factory,
    cashdesk_session_before_factory,
    item_factory,
    user_factory,
)


@pytest.mark.django_db
def test_backoffice_can_create_session(backoffice_client):
    assert CashdeskSession.objects.count() == 0
    response = backoffice_client.get(
        "/backoffice/session/new/?desk={}".format(cashdesk_factory().pk)
    )
    assert response.status_code == 200
    response = backoffice_client.post(
        "/backoffice/session/new/",
        {
            "session-cashdesk": cashdesk_factory().pk,
            "session-user": user_factory(),
            "session-backoffice_user": user_factory(backoffice=True),
            "session-cash_before": "10.00",
            "items-0-item": item_factory().pk,
            "items-0-amount": "5",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
        },
        follow=True,
    )
    assert response.status_code == 200
    assert CashdeskSession.objects.count() == 1


@pytest.mark.django_db
def test_backoffice_cannot_create_session_faulty_data(backoffice_client):
    assert CashdeskSession.objects.count() == 0
    response = backoffice_client.post(
        "/backoffice/session/new/",
        {
            "session-cashdesk": cashdesk_factory().pk,
            "session-user": user_factory(),
            "session-backoffice_user": user_factory(backoffice=True),
            "session-cash_before": "10.00",
            "items-0-item": item_factory().pk + 1,
            "items-0-amount": "1",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
        },
        follow=True,
    )
    assert response.status_code == 200
    assert CashdeskSession.objects.count() == 0
    assert "Session could not be created" in response.content.decode()


@pytest.mark.django_db
def test_can_see_cashdesk_session(backoffice_client):
    session = cashdesk_session_before_factory()
    response = backoffice_client.get("/backoffice/session/{}/".format(session.pk))
    assert response.status_code == 200


@pytest.mark.django_db
def test_backoffice_can_resupply(backoffice_client):
    session = cashdesk_session_before_factory()
    cash_before = session.cash_before
    response = backoffice_client.post(
        "/backoffice/session/{}/resupply/".format(session.pk),
        {
            "session-cashdesk": cashdesk_factory().pk,
            "session-user": user_factory(),
            "session-backoffice_user": user_factory(backoffice=True),
            "session-cash_before": "10.00",
            "items-0-item": session.item_movements.first().item.pk,
            "items-0-amount": "1",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
        },
        follow=True,
    )
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.cash_before == cash_before + 10


@pytest.mark.django_db
def test_backoffice_can_end_and_correct_session(backoffice_client):
    session = cashdesk_session_before_factory()
    response = backoffice_client.get("/backoffice/session/{}/end/".format(session.pk))
    assert response.status_code == 200
    response = backoffice_client.post(
        "/backoffice/session/{}/end/".format(session.pk),
        {
            "session-cashdesk": cashdesk_factory().pk,
            "session-user": user_factory(),
            "session-backoffice_user": user_factory(backoffice=True),
            "session-cash_before": "10.00",
            "items-0-item": session.item_movements.first().item.pk,
            "items-0-amount": "1",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
        },
        follow=True,
    )
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.end
    response = backoffice_client.get("/backoffice/session/{}/end/".format(session.pk))
    assert response.status_code == 200
    response = backoffice_client.post(
        "/backoffice/session/{}/end/".format(session.pk),
        {
            "session-cashdesk": cashdesk_factory().pk,
            "session-user": user_factory(),
            "session-backoffice_user": user_factory(backoffice=True),
            "session-cash_before": "20.00",
            "items-0-item": session.item_movements.first().item.pk,
            "items-0-amount": "1",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
        },
        follow=True,
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_backoffice_can_see_record(backoffice_client):
    session = cashdesk_session_after_factory()
    response = backoffice_client.get(
        "/backoffice/records/{}/print/".format(session.final_cash_movement.record.pk)
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_backoffice_can_move_session(backoffice_client):
    session = cashdesk_session_before_factory()
    desk = session.cashdesk
    response = backoffice_client.get("/backoffice/session/{}/move/".format(session.pk))
    assert response.status_code == 200
    response = backoffice_client.post(
        "/backoffice/session/{}/move/".format(session.pk),
        {
            "session-cashdesk": cashdesk_factory().pk,
            "session-user": user_factory(),
            "session-backoffice_user": user_factory(backoffice=True),
            "session-cash_before": "10.00",
        },
        follow=True,
    )
    assert response.status_code == 200
    assert "Session has been moved" in response.content.decode()
    session.refresh_from_db()
    assert session.cashdesk != desk
