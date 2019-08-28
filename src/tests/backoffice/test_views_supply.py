import pytest

from postix.core.models.base import ItemSupplyPack

from ..factories import item_factory, itemsupplypack_factory


@pytest.mark.django_db
def test_backoffice_supply_list(event_settings, backoffice_client):
    itemsupplypack_factory()
    response = backoffice_client.get("/backoffice/supplies/")
    assert response.status_code == 200
    assert "5KzLPML2L1ij52cl93VduM4cdOjuYz" in response.rendered_content


@pytest.mark.django_db
def test_backoffice_supply_create(event_settings, backoffice_client):
    item = item_factory()
    response = backoffice_client.post(
        "/backoffice/supplies/create/",
        data={
            "identifier": "/supply 5KzLPML2L1ij52cl93VduM4cdOjuYz",
            "amount": "50",
            "item": str(item.pk),
        },
    )
    assert response.status_code == 302
    isp = ItemSupplyPack.objects.last()
    assert isp.identifier == "/supply 5KzLPML2L1ij52cl93VduM4cdOjuYz"
    assert isp.amount == 50
    assert isp.item == item
    assert isp.logs.count() == 1


@pytest.mark.django_db
def test_backoffice_supply_create_invalid_identifier(event_settings, backoffice_client):
    item = item_factory()
    response = backoffice_client.post(
        "/backoffice/supplies/create/",
        data={
            "identifier": "5KzLPML2L1ij52cl93VduM4cdOjuYz",
            "amount": "50",
            "item": str(item.pk),
        },
    )
    assert response.status_code == 200
    assert "error" in response.rendered_content


@pytest.mark.django_db
def test_backoffice_supply_out(event_settings, backoffice_client):
    isp = itemsupplypack_factory(state="backoffice")
    response = backoffice_client.post(
        "/backoffice/supplies/out/", data={"identifier": isp.identifier}
    )
    assert response.status_code == 302
    isp.refresh_from_db()
    assert isp.state == "troubleshooter"
    assert isp.logs.count() == 1


@pytest.mark.django_db
def test_backoffice_supply_out_invalid_state(event_settings, backoffice_client):
    isp = itemsupplypack_factory(state="used")
    response = backoffice_client.post(
        "/backoffice/supplies/out/", data={"identifier": isp.identifier}
    )
    assert response.status_code == 200
    isp.refresh_from_db()
    assert isp.state == "used"
    assert isp.logs.count() == 0


@pytest.mark.django_db
def test_backoffice_supply_in(event_settings, backoffice_client):
    isp = itemsupplypack_factory(state="troubleshooter")
    response = backoffice_client.post(
        "/backoffice/supplies/in/", data={"identifier": isp.identifier}
    )
    assert response.status_code == 302
    isp.refresh_from_db()
    assert isp.state == "backoffice"
    assert isp.logs.count() == 1


@pytest.mark.django_db
def test_backoffice_supply_in_invalid_state(event_settings, backoffice_client):
    isp = itemsupplypack_factory(state="used")
    response = backoffice_client.post(
        "/backoffice/supplies/in/", data={"identifier": isp.identifier}
    )
    assert response.status_code == 200
    isp.refresh_from_db()
    assert isp.state == "used"
    assert isp.logs.count() == 0


@pytest.mark.django_db
def test_backoffice_supply_dissolve(event_settings, backoffice_client):
    isp = itemsupplypack_factory(state="backoffice")
    response = backoffice_client.post(
        "/backoffice/supplies/away/", data={"identifier": isp.identifier}
    )
    assert response.status_code == 302
    isp.refresh_from_db()
    assert isp.state == "dissolved"
    assert isp.logs.count() == 1


@pytest.mark.django_db
def test_backoffice_supply_away_invalid_state(event_settings, backoffice_client):
    isp = itemsupplypack_factory(state="used")
    response = backoffice_client.post(
        "/backoffice/supplies/away/", data={"identifier": isp.identifier}
    )
    assert response.status_code == 200
    isp.refresh_from_db()
    assert isp.state == "used"
    assert isp.logs.count() == 0
