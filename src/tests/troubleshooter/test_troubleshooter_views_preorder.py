import pytest

from postix.core.utils import times

from ..factories import cashdesk_factory, preorder_factory, preorder_position_factory


@pytest.mark.django_db
def test_cannot_see_all_preorders(troubleshooter_client):
    preorders = [preorder_factory() for _ in times(3)]
    response = troubleshooter_client.get("/troubleshooter/preorders/")
    assert response.status_code == 200
    content = response.content.decode()
    for preorder in preorders:
        assert preorder.order_code not in content


@pytest.mark.django_db
def test_cannot_filter_for_short_preorder_code(troubleshooter_client):
    preorders = [preorder_factory() for _ in times(3)]
    response = troubleshooter_client.get(
        "/troubleshooter/preorders/?code=" + preorders[0].order_code[:2]
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "You need to enter at least four characters of the order code." in content
    for preorder in preorders:
        assert preorder.order_code not in content


@pytest.mark.django_db
def test_can_filter_for_preorder_code(troubleshooter_client):
    preorders = [preorder_factory() for _ in times(3)]
    response = troubleshooter_client.get(
        "/troubleshooter/preorders/?code=" + preorders[0].order_code[:6]
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert preorders[0].order_code in content
    for preorder in preorders[1:]:
        assert preorder.order_code not in content


@pytest.mark.django_db
def test_can_see_preorder_informations(troubleshooter_client):
    positions = [
        preorder_position_factory(information="Speaker {}".format(index), redeemed=True)
        for index in range(3)
    ]
    other_positions = [preorder_position_factory(redeemed=True) for _ in times(2)]
    response = troubleshooter_client.get("/troubleshooter/preorders/information/")
    assert response.status_code == 200
    content = response.content.decode()
    for position in positions:
        assert position.preorder.order_code in content
    for position in other_positions:
        assert position.preorder.order_code not in content


@pytest.mark.django_db
def test_cannot_print_preorder_information_without_cashdesk(troubleshooter_client):
    [
        preorder_position_factory(information="Speaker {}".format(index), redeemed=True)
        for index in range(3)
    ]
    [preorder_position_factory(redeemed=True) for _ in times(2)]
    response = troubleshooter_client.post(
        "/troubleshooter/preorders/information/", follow=True
    )
    assert response.status_code == 200
    assert "Please specify a cashdesk." in response.content.decode()


@pytest.mark.django_db
def test_can_print_preorder_information_from_cashdesk(troubleshooter_client):
    [
        preorder_position_factory(information="Speaker {}".format(index), redeemed=True)
        for index in range(3)
    ]
    [preorder_position_factory(redeemed=True) for _ in times(2)]
    cashdesk = cashdesk_factory()
    response = troubleshooter_client.post(
        "/troubleshooter/preorders/information/", {"cashdesk": cashdesk.pk}, follow=True
    )
    assert response.status_code == 200
    assert "Attendance print in progress." in response.content.decode()
