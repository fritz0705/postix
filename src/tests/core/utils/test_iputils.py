import pytest
from django.test import RequestFactory

from postix.core.utils.iputils import detect_cashdesk, get_ip_address

from ...factories import cashdesk_factory


def get_req_with_ip(ip):
    factory = RequestFactory()
    request = factory.get("/")
    request.META["REMOTE_ADDR"] = ip
    return request


def test_ip_addr_forwarded_for():
    request = get_req_with_ip("10.1.2.4")
    request.META["HTTP_X_FORWARDED_FOR"] = "10.1.2.3"
    assert get_ip_address(request) == "10.1.2.3"


def test_ip_addr_direct():
    request = get_req_with_ip("10.1.2.4")
    assert get_ip_address(request) == "10.1.2.4"


@pytest.mark.django_db
def test_detect_cashdesk_none():
    request = get_req_with_ip("10.1.2.4")
    assert detect_cashdesk(request) is None


@pytest.mark.django_db
def test_detect_cashdesk_active():
    request = get_req_with_ip("10.1.2.4")
    cashdesk = cashdesk_factory(ip="10.1.2.4", active=True)
    assert detect_cashdesk(request) == cashdesk


@pytest.mark.django_db
def test_detect_cashdesk_inactive():
    request = get_req_with_ip("10.1.2.4")
    cashdesk_factory(ip="10.1.2.4", active=False)
    assert detect_cashdesk(request) is None
