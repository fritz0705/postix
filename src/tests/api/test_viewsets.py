import json

import pytest

from ..factories import (
    list_constraint_entry_factory,
    list_constraint_factory,
    preorder_position_factory,
)


@pytest.mark.django_db
def test_preorders(api_with_session):
    preorder_position_factory(paid=True)
    response = api_with_session.get("/api/preorderpositions/")
    content = json.loads(response.content.decode())
    assert content["count"] == 0


@pytest.mark.django_db
def test_preorders_with_secret(api_with_session):
    pp = preorder_position_factory(paid=True)
    response = api_with_session.get("/api/preorderpositions/?secret=" + pp.secret)
    content = json.loads(response.content.decode())
    assert content["count"] == 1


@pytest.mark.django_db
@pytest.mark.parametrize("chars", [1, 6, 10])
def test_preorders_with_search(api_with_session, chars):
    pp = preorder_position_factory(paid=True)
    response = api_with_session.get(
        "/api/preorderpositions/?search=" + pp.secret[:chars]
    )
    content = json.loads(response.content.decode())
    assert content["count"] == int(chars >= 6)


@pytest.mark.django_db
def test_listentries(api_with_session):
    list_constraint_entry_factory(list_constraint_factory())
    response = api_with_session.get("/api/listconstraintentries/")
    content = json.loads(response.content.decode())
    assert content["count"] == 0


@pytest.mark.django_db
def test_listentries_with_id(api_with_session):
    constraint = list_constraint_entry_factory(list_constraint_factory())
    response = api_with_session.get(
        "/api/listconstraintentries/?listid=" + str(constraint.list_id)
    )
    content = json.loads(response.content.decode())
    assert content["count"] == 0


@pytest.mark.django_db
@pytest.mark.parametrize("chars", [1, 6, 100])
def test_listentries_with_search(api_with_session, chars):
    constraint = list_constraint_entry_factory(list_constraint_factory())
    response = api_with_session.get(
        "/api/listconstraintentries/?listid="
        + str(constraint.list_id)
        + "&search="
        + constraint.identifier[:chars]
    )
    content = json.loads(response.content.decode())
    assert content["count"] == int(chars >= 3)
