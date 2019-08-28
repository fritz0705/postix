import pytest

from postix.core.models import User

from ...factories import user_factory


@pytest.mark.django_db
def test_create_user():
    u = User.objects.create_user("foo", "bar")
    assert u.pk
    assert u.username == "foo"
    assert u.check_password("bar")
    assert not u.is_superuser
    assert not u.is_troubleshooter


@pytest.mark.django_db
def test_create_superuser():
    u = User.objects.create_superuser("foo", "bar")
    assert u.pk
    assert u.username == "foo"
    assert u.check_password("bar")
    assert u.is_superuser
    assert u.is_troubleshooter


@pytest.mark.django_db
def test_user_is_staff():
    assert user_factory(troubleshooter=True).is_staff
    assert user_factory(superuser=True).is_staff
    assert not user_factory().is_staff
