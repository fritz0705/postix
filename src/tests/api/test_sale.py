import json

import pytest

from postix.core.models import ListConstraintProduct, WarningConstraintProduct
from postix.core.utils.checks import is_redeemed

from ..factories import (
    list_constraint_entry_factory,
    list_constraint_factory,
    product_factory,
    quota_factory,
    user_factory,
    warning_constraint_factory,
)


def help_test_for_error(api, product, options=None):
    req = {"positions": [{"type": "sell", "product": product.id}]}
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
    class FakeProd:
        id = 0

    assert help_test_for_error(api_with_session, FakeProd()) == {
        "success": False,
        "message": "This product ID is not known.",
        "type": "error",
        "missing_field": None,
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_sell_warning_constraint(api_with_session):
    p = product_factory()
    warning_constraint = warning_constraint_factory()
    WarningConstraintProduct.objects.create(product=p, constraint=warning_constraint)
    assert help_test_for_error(api_with_session, p) == {
        "success": False,
        "message": warning_constraint.message,
        "type": "confirmation",
        "missing_field": "warning_{}_acknowledged".format(warning_constraint.pk),
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_sell_list_constraint(api_with_session):
    p = product_factory()
    list_constraint = list_constraint_factory()
    ListConstraintProduct.objects.create(product=p, constraint=list_constraint)
    assert help_test_for_error(api_with_session, p) == {
        "success": False,
        "message": 'This ticket can only redeemed by persons on the list "{}".'.format(
            list_constraint.name
        ),
        "type": "input",
        "missing_field": "list_{}".format(list_constraint.pk),
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_sell_list_constraint_unknown(api_with_session):
    p = product_factory()
    list_constraint = list_constraint_factory()
    ListConstraintProduct.objects.create(product=p, constraint=list_constraint)
    options = {"list_{}".format(list_constraint.pk): "2"}
    assert help_test_for_error(api_with_session, p, options) == {
        "success": False,
        "message": 'This entry could not be found in list "{}".'.format(
            list_constraint.name
        ),
        "type": "input",
        "missing_field": "list_{}".format(list_constraint.pk),
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_sell_list_constraint_used(api_with_session):
    p = product_factory()
    list_constraint = list_constraint_factory()
    entry = list_constraint_entry_factory(
        list_constraint=list_constraint, redeemed=True
    )
    ListConstraintProduct.objects.create(product=p, constraint=entry.list)
    options = {"list_{}".format(entry.list.pk): str(entry.identifier)}
    assert help_test_for_error(api_with_session, p, options) == {
        "success": False,
        "message": "This list entry has already been used.",
        "type": "input",
        "missing_field": "list_{}".format(entry.list.pk),
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_sell_quota_failed_allow_override(api_with_session):
    p = product_factory()
    q = quota_factory(size=0)
    q.products.add(p)
    assert help_test_for_error(api_with_session, p) == {
        "success": False,
        "message": "This product is currently unavailable or sold out.",
        "type": "input",
        "missing_field": "auth",
        "bypass_price": None,
    }
    u = user_factory(troubleshooter=True)
    req = {"positions": [{"type": "sell", "product": p.id, "auth": u.auth_token}]}
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 201
    j = json.loads(response.content.decode())
    assert j["success"]


@pytest.mark.django_db
def test_require_auth(api_with_session):
    p = product_factory()
    p.requires_authorization = True
    p.save()
    assert help_test_for_error(api_with_session, p) == {
        "success": False,
        "message": "This sale requires authorization by a troubleshooter.",
        "type": "input",
        "missing_field": "auth",
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_require_auth_invalid(api_with_session):
    p = product_factory()
    p.requires_authorization = True
    p.save()
    assert help_test_for_error(api_with_session, p) == {
        "success": False,
        "message": "This sale requires authorization by a troubleshooter.",
        "type": "input",
        "missing_field": "auth",
        "bypass_price": None,
    }


@pytest.mark.django_db
def test_require_auth_valid(api_with_session):
    p = product_factory()
    p.requires_authorization = True
    p.save()
    u = user_factory(troubleshooter=True)
    req = {"positions": [{"type": "sell", "product": p.id, "auth": u.auth_token}]}
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 201
    j = json.loads(response.content.decode())
    assert j["success"]


@pytest.mark.django_db
def test_sell_quota_partially(api_with_session):
    p = product_factory()
    q = quota_factory(size=1)
    q.products.add(p)
    req = {
        "positions": [
            {"type": "sell", "product": p.id},
            {"type": "sell", "product": p.id},
        ]
    }
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 400
    j = json.loads(response.content.decode())
    assert not j["success"]


@pytest.mark.django_db
def test_sell_list_constraint_override(api_with_session):
    p = product_factory()
    list_constraint = list_constraint_factory()
    entry = list_constraint_entry_factory(
        list_constraint=list_constraint, redeemed=False
    )
    ListConstraintProduct.objects.create(product=p, constraint=entry.list)
    bu = user_factory(troubleshooter=True)
    req = {
        "positions": [
            {
                "type": "sell",
                "list_{}".format(entry.list.pk): bu.auth_token,
                "product": p.id,
            }
        ]
    }
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 201
    j = json.loads(response.content.decode())
    assert j["success"]
    assert j["positions"][0]["success"]


@pytest.mark.django_db
def test_sell_list_constraint_success(api_with_session):
    p = product_factory()
    list_constraint = list_constraint_factory()
    entry = list_constraint_entry_factory(
        list_constraint=list_constraint, redeemed=False
    )
    ListConstraintProduct.objects.create(product=p, constraint=entry.list)
    req = {
        "positions": [
            {
                "type": "sell",
                "list_{}".format(entry.list.pk): str(entry.identifier),
                "product": p.id,
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
def test_fail_on_empty(api_with_session, event_settings):
    p = product_factory()
    q = quota_factory(size=99)
    q.products.add(p)
    req = {"cash_given": "10.00"}
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 400
    j = json.loads(response.content.decode())
    assert isinstance(j, str)


@pytest.mark.django_db
def test_success(api_with_session, event_settings):
    p = product_factory()
    q = quota_factory(size=99)
    q.products.add(p)
    req = {"cash_given": "10.00", "positions": [{"type": "sell", "product": p.id}]}
    response = api_with_session.post("/api/transactions/", req, format="json")
    assert response.status_code == 201
    j = json.loads(response.content.decode())
    assert j["success"]
    assert j["positions"][0]["success"]
