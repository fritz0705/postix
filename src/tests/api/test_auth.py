from datetime import timedelta

import pytest
from django.utils.timezone import now

from ..factories import cashdesk_session_before_factory


def test_no_token(api):
    r = api.get("/api/preorders/")
    assert r.status_code == 401
    assert "not provided" in r.content.decode("utf-8")


@pytest.mark.django_db
def test_invalid_token(api):
    api.credentials(HTTP_AUTHORIZATION="Token 1234")
    r = api.get("/api/preorders/")
    assert r.status_code == 401
    assert "Invalid token" in r.content.decode("utf-8")


@pytest.mark.django_db
def test_inactive_session(api):
    session = cashdesk_session_before_factory()
    session.end = now() - timedelta(hours=1)
    session.save()
    api.credentials(HTTP_AUTHORIZATION="Token " + session.api_token)
    r = api.get("/api/preorders/")
    assert r.status_code == 401
    assert "has ended" in r.content.decode("utf-8")


@pytest.mark.django_db
def test_wrong_cashdesk(api):
    session = cashdesk_session_before_factory()
    session.save()
    session.cashdesk.ip_address = "10.1.1.1"
    session.cashdesk.save()
    api.credentials(HTTP_AUTHORIZATION="Token " + session.api_token)
    r = api.get("/api/preorders/")
    assert r.status_code == 401
    assert "different cashdesk" in r.content.decode("utf-8")


@pytest.mark.django_db
def test_valid(api):
    session = cashdesk_session_before_factory(ip="127.0.0.1")
    api.credentials(HTTP_AUTHORIZATION="Token " + session.api_token)
    r = api.get("/api/preorders/")
    assert r.status_code in (403, 200)
