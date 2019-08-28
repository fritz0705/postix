import json

import pytest

from postix.core.utils import times

from ..factories import notification_factory


@pytest.mark.parametrize("amount", (0, 1, 2))
@pytest.mark.django_db
def test_check_requests_without_requests(amount, troubleshooter_client):
    [notification_factory() for _ in times(amount)]
    response = troubleshooter_client.get("/troubleshooter/session/check_requests")
    assert response.status_code == 200
    content = json.loads(response.content.decode())
    assert content == {"has_requests": bool(amount)}


@pytest.mark.django_db
def test_confirm_resupply(troubleshooter_client):
    notification = notification_factory()
    response = troubleshooter_client.get(
        "/troubleshooter/session/{}/resupply/".format(notification.session.pk)
    )
    response = troubleshooter_client.post(
        "/troubleshooter/session/{}/resupply/".format(notification.session.pk),
        follow=True,
    )
    assert response.status_code == 200
    assert "resupplied" in response.content.decode()
    notification.refresh_from_db()
    assert notification.status == "ACK"


@pytest.mark.django_db
def test_confirm_resupply_incorrect_session(troubleshooter_client):
    notification = notification_factory()
    response = troubleshooter_client.post(
        "/troubleshooter/session/{}/resupply/".format(notification.session.pk + 1),
        follow=True,
    )
    assert response.status_code == 200
    assert "Unknown session" in response.content.decode()
    notification.refresh_from_db()
    assert notification.status != "ACK"
