import json

import pytest

from postix.core.models import ListConstraintProduct, WarningConstraintProduct
from postix.core.utils.checks import is_redeemed

from ..factories import (
    list_constraint_entry_factory,
    list_constraint_factory,
    preorder_position_factory,
    user_factory,
    warning_constraint_factory,
)


def help_test_for_error(api, secret, options=None):
    req = {"positions": [{"type": "redeem", "secret": secret}]}
    if options:
        req["positions"][0].update(options)
    response = api.post("/api/transactions/", req, format="json")
    assert response.status_code == 400
    j = json.loads(response.content.decode())
    assert not j["success"]
    assert not j["positions"][0]["success"]
    return j["positions"][0]


@pytest.mark.django_db
def test_invalid(api_with_session):
    assert help_test_for_error(api_with_session, "abcde") == {
        "success": False,
        "message": "No ticket could be found with the given secret.",
        "type": "error",
        "missing_field": None,
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_canceled(api_with_session):
    assert help_test_for_error(
        api_with_session, preorder_position_factory(canceled=True).secret
    ) == {
        "success": False,
        "message": "This ticket has been canceled or is expired.",
        "type": "error",
        "missing_field": None,
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_already_redeemed(api_with_session):
    d = help_test_for_error(
        api_with_session, preorder_position_factory(paid=True, redeemed=True).secret
    )
    assert d["success"] is False
    assert "already been redeemed" in d["message"]
    assert d["type"] == "error"


@pytest.mark.django_db
def test_preorder_warning(api_with_session):
    pp = preorder_position_factory(paid=True)
    pp.preorder.warning_text = "Foo"
    pp.preorder.save()
    assert help_test_for_error(api_with_session, pp.secret) == {
        "success": False,
        "message": "Foo",
        "type": "confirmation",
        "missing_field": "warning_acknowledged",
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_preorder_warning_constraint(api_with_session):
    pp = preorder_position_factory(paid=True)
    warning_constraint = warning_constraint_factory()
    WarningConstraintProduct.objects.create(
        product=pp.product, constraint=warning_constraint
    )
    assert help_test_for_error(api_with_session, pp.secret) == {
        "success": False,
        "message": warning_constraint.message,
        "type": "confirmation",
        "missing_field": "warning_{}_acknowledged".format(warning_constraint.pk),
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_preorder_list_constraint(api_with_session):
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory()
    ListConstraintProduct.objects.create(product=pp.product, constraint=list_constraint)
    assert help_test_for_error(api_with_session, pp.secret) == {
        "success": False,
        "message": 'This ticket can only redeemed by persons on the list "{}".'.format(
            list_constraint.name
        ),
        "type": "input",
        "missing_field": "list_{}".format(list_constraint.pk),
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_preorder_list_constraint_unknown(api_with_session):
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory()
    ListConstraintProduct.objects.create(product=pp.product, constraint=list_constraint)
    options = {"list_{}".format(list_constraint.pk): "2"}
    assert help_test_for_error(api_with_session, pp.secret, options) == {
        "success": False,
        "message": 'This entry could not be found in list "{}".'.format(
            list_constraint.name
        ),
        "type": "input",
        "missing_field": "list_{}".format(list_constraint.pk),
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_preorder_list_constraint_used(api_with_session):
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory()
    entry = list_constraint_entry_factory(
        list_constraint=list_constraint, redeemed=True
    )
    ListConstraintProduct.objects.create(product=pp.product, constraint=entry.list)
    options = {"list_{}".format(entry.list.pk): str(entry.identifier)}
    assert help_test_for_error(api_with_session, pp.secret, options) == {
        "success": False,
        "message": "This list entry has already been used.",
        "type": "input",
        "missing_field": "list_{}".format(entry.list.pk),
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_preorder_list_constraint_override(api_with_session):
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory()
    entry = list_constraint_entry_factory(
        list_constraint=list_constraint, redeemed=False
    )
    ListConstraintProduct.objects.create(product=pp.product, constraint=entry.list)
    u = user_factory(troubleshooter=True)
    req = {
        "positions": [
            {
                "type": "redeem",
                "list_{}".format(entry.list.pk): u.auth_token,
                "secret": pp.secret,
            }
        ]
    }
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 201
    j = json.loads(response.content.decode())
    assert j["success"]
    assert j["positions"][0]["success"]


@pytest.mark.django_db
def test_preorder_list_constraint_success(api_with_session):
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory()
    entry = list_constraint_entry_factory(
        list_constraint=list_constraint, redeemed=False
    )
    ListConstraintProduct.objects.create(product=pp.product, constraint=entry.list)
    req = {
        "positions": [
            {
                "type": "redeem",
                "list_{}".format(entry.list.pk): str(entry.identifier),
                "secret": pp.secret,
            }
        ]
    }
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 201
    j = json.loads(response.content.decode())
    assert j["success"]
    assert j["positions"][0]["success"]
    assert is_redeemed(entry)


@pytest.mark.django_db
def test_twice_in_cart(api_with_session, event_settings):
    pp = preorder_position_factory(paid=True)
    secret = pp.secret
    req = {
        "positions": [
            {"type": "redeem", "secret": secret},
            {"type": "redeem", "secret": secret},
        ]
    }
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 400
    j = json.loads(response.content.decode())
    assert not j["success"]
    assert not is_redeemed(pp)


@pytest.mark.django_db
def test_list_constraint_bypass_success(api_with_session, event_settings):
    pp = preorder_position_factory(paid=True)
    list_constraint = list_constraint_factory()
    entry = list_constraint_entry_factory(
        list_constraint=list_constraint, redeemed=True
    )
    ListConstraintProduct.objects.create(
        product=pp.product, constraint=entry.list, price=10
    )
    req = {
        "positions": [{"type": "redeem", "secret": pp.secret, "bypass_price": "10.00"}]
    }
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 201
    j = json.loads(response.content.decode())
    assert j["success"]
    assert j["positions"][0]["success"]
    assert is_redeemed(pp)


@pytest.mark.django_db
def test_warning_constraint_bypass_success(api_with_session, event_settings):
    pp = preorder_position_factory(paid=True)
    warning_constraint = warning_constraint_factory()
    WarningConstraintProduct.objects.create(
        product=pp.product, constraint=warning_constraint, price=65
    )
    req = {
        "positions": [{"type": "redeem", "secret": pp.secret, "bypass_price": "65.00"}]
    }
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 201
    j = json.loads(response.content.decode())
    assert j["success"]
    assert j["positions"][0]["success"]
    assert is_redeemed(pp)


@pytest.mark.django_db
def test_success(api_with_session, event_settings):
    pp = preorder_position_factory(paid=True)
    secret = pp.secret
    req = {"positions": [{"type": "redeem", "secret": secret}]}
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 201
    j = json.loads(response.content.decode())
    assert j["success"]
    assert j["positions"][0]["success"]
    assert is_redeemed(pp)


@pytest.mark.django_db
def test_success_unpaid(api_with_session, event_settings):
    pp = preorder_position_factory(paid=False, price=23.42)
    secret = pp.secret
    req = {"positions": [{"type": "redeem", "secret": secret}]}
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 400
    j = json.loads(response.content.decode())
    assert not j["success"]
    assert not j["positions"][0]["success"]
    req = {"positions": [{"type": "redeem", "secret": secret, "bypass_price": "23.42"}]}
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 201
    j = json.loads(response.content.decode())
    assert j["success"]
    assert j["positions"][0]["success"]
