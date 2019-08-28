import pytest

from postix.core.models import Record, RecordEntity

from ..factories import (
    cashdesk_session_after_factory,
    record_entity_factory,
    record_factory,
    user_factory,
)


@pytest.mark.django_db
def test_backoffice_record_list(backoffice_client):
    cashdesk_session_after_factory()
    record_factory(incoming=True)
    record_factory(incoming=False)
    response = backoffice_client.get("/backoffice/records/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_backoffice_record_detail(backoffice_client):
    record = record_factory(incoming=True)
    response = backoffice_client.get("/backoffice/records/{}/".format(record.pk))
    assert response.status_code == 200


@pytest.mark.django_db
def test_backoffice_record_edit(backoffice_client):
    record = record_factory(incoming=True)
    response = backoffice_client.post(
        "/backoffice/records/{}/?edit".format(record.pk),
        {
            "type": "outflow",
            "datetime": "",
            "entity": record.entity.pk,
            "carrier": "testttt",
            "amount": "10.00",
            "backoffice_user": record.backoffice_user.username,
        },
        follow=True,
    )
    assert response.status_code == 200
    record.refresh_from_db()
    assert record.type == "outflow"


@pytest.mark.django_db
def test_backoffice_create_record(backoffice_client):
    entity = record_entity_factory()
    backoffice_user = user_factory(backoffice=True)
    assert Record.objects.count() == 0
    response = backoffice_client.post(
        "/backoffice/records/new/",
        {
            "type": "inflow",
            "datetime": "",
            "entity": entity.pk,
            "carrier": "testttt",
            "amount": "10.00",
            "backoffice_user": backoffice_user.username,
        },
        follow=True,
    )
    assert response.status_code == 200
    assert Record.objects.count() == 1


@pytest.mark.django_db
def test_backoffice_create_record_entity(superuser_client, event_settings):
    assert RecordEntity.objects.count() == 0
    response = superuser_client.post(
        "/backoffice/records/entity/new/",
        {"name": "testname", "detail": "testdetail"},
        follow=True,
    )
    assert response.status_code == 200
    assert RecordEntity.objects.count() == 1


@pytest.mark.django_db
def test_backoffice_edit_record_entity(superuser_client, event_settings):
    entity = record_entity_factory()
    response = superuser_client.get("/backoffice/records/entity/{}/".format(entity.pk))
    assert response.status_code == 200
    response = superuser_client.post(
        "/backoffice/records/entity/{}/".format(entity.pk),
        {"name": "testname", "detail": "testdetail"},
        follow=True,
    )
    assert response.status_code == 200
    entity.refresh_from_db()
    assert entity.name == "testname"


@pytest.mark.django_db
def test_backoffice_delete_record_entity(superuser_client, event_settings):
    entity = record_entity_factory()
    assert RecordEntity.objects.count() == 1
    response = superuser_client.post(
        "/backoffice/records/entity/{}/delete/".format(entity.pk), follow=True
    )
    assert response.status_code == 200
    assert RecordEntity.objects.count() == 0
