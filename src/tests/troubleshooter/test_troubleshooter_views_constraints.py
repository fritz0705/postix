import pytest

from ..factories import list_constraint_entry_factory, list_constraint_factory


@pytest.mark.django_db
def test_troubleshooter_can_see_all_entries(troubleshooter_client):
    constraint = list_constraint_factory()
    entries = [list_constraint_entry_factory(constraint) for _ in range(3)]
    response = troubleshooter_client.get(
        "/troubleshooter/constraints/{}/".format(constraint.pk)
    )
    assert response.status_code == 200
    content = response.content.decode()
    for entry in entries:
        assert entry.name in content


@pytest.mark.django_db
def test_troubleshooter_cannot_see_entries_if_confidential(troubleshooter_client):
    constraint = list_constraint_factory(confidential=True)
    entries = [list_constraint_entry_factory(constraint) for _ in range(3)]
    response = troubleshooter_client.get(
        "/troubleshooter/constraints/{}/".format(constraint.pk)
    )
    assert response.status_code == 200
    content = response.content.decode()
    for entry in entries:
        assert entry.name not in content


@pytest.mark.django_db
def test_troubleshooter_can_filter_all_entries(troubleshooter_client):
    constraint = list_constraint_factory()
    entries = [list_constraint_entry_factory(constraint) for _ in range(3)]
    query = entries[0].name[:1]
    response = troubleshooter_client.get(
        "/troubleshooter/constraints/{}/?filter={}".format(constraint.pk, query)
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert entries[0].name in content


@pytest.mark.django_db
def test_troubleshooter_cannot_filter_entries_if_confidential_and_too_short(
    troubleshooter_client
):
    constraint = list_constraint_factory(confidential=True)
    entries = [list_constraint_entry_factory(constraint) for _ in range(3)]
    query = entries[0].name[:1]
    response = troubleshooter_client.get(
        "/troubleshooter/constraints/{}/?filter={}".format(constraint.pk, query)
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert entries[0].name not in content


@pytest.mark.django_db
def test_troubleshooter_can_filter_entries_if_confidential_and_long_enough(
    troubleshooter_client
):
    constraint = list_constraint_factory(confidential=True)
    entries = [list_constraint_entry_factory(constraint) for _ in range(3)]
    query = entries[0].name[:5]
    response = troubleshooter_client.get(
        "/troubleshooter/constraints/{}/?filter={}".format(constraint.pk, query)
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert entries[0].name in content
