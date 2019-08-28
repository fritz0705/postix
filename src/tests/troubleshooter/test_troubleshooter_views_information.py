import pytest

from ..factories import cashdesk_factory, information_factory


@pytest.mark.django_db
def test_troubleshooter_print_information(troubleshooter_client):
    info = information_factory()
    desk = cashdesk_factory()
    response = troubleshooter_client.post(
        "/troubleshooter/information/{}/".format(info.pk),
        {"cashdesk": desk.pk, "amount": 2},
        follow=True,
    )
    assert response.status_code == 200
    assert "Done." in response.content.decode()


@pytest.mark.django_db
def test_troubleshooter_print_information_incorrect_data(troubleshooter_client):
    info = information_factory()
    desk = cashdesk_factory()
    response = troubleshooter_client.post(
        "/troubleshooter/information/{}/".format(info.pk),
        {"cashdesk": desk.pk, "amount": -1},
        follow=True,
    )
    assert response.status_code == 200
    assert "Done." not in response.content.decode()
