import pytest
from django.contrib.auth.models import AnonymousUser

from postix.core.models import TroubleshooterNotification
from postix.troubleshooter.views.utils import troubleshooter_user

from ..factories import user_factory


@pytest.mark.parametrize(
    "url,expected",
    (
        ("/backoffice/", 302),
        ("/troubleshooter/", 200),
        ("/troubleshooter/transactions/", 200),
        ("/troubleshooter/constraints/", 200),
        ("/troubleshooter/preorders/", 200),
        ("/troubleshooter/preorders/information/", 200),
        ("/troubleshooter/ping/", 200),
        ("/troubleshooter/information/", 200),
    ),
)
@pytest.mark.django_db
def test_can_access_pages(troubleshooter_client, url, expected):
    response = troubleshooter_client.get(url)
    assert response.status_code == expected
    if expected == 200:
        assert "Troubleshooter" in response.content.decode()


@pytest.mark.django_db
def test_shows_troubleshooter_notification(troubleshooter_client):
    from ..factories import user_factory, cashdesk_session_before_factory

    user = user_factory()
    TroubleshooterNotification.objects.create(
        session=cashdesk_session_before_factory(user=user),
        modified_by=user,
        message="Requesting resupply",
    )
    response = troubleshooter_client.get("/troubleshooter/")
    assert (
        'class="nav-link nav-link-second-level has-request' in response.content.decode()
    )


@pytest.mark.django_db
def test_troubleshooter_user_method():
    assert troubleshooter_user(user_factory(troubleshooter=True))
    assert not troubleshooter_user(user_factory())
    assert not troubleshooter_user(user_factory(superuser=True))
    assert not troubleshooter_user(AnonymousUser)
