import pytest
from django.contrib.auth import authenticate, get_user_model

from ..factories import user_factory

User = get_user_model()


@pytest.mark.parametrize("is_backoffice_user", (True, False))
@pytest.mark.django_db
def test_backoffice_can_create_normal_user(backoffice_client, is_backoffice_user):
    count = User.objects.count()
    response = backoffice_client.post(
        "/backoffice/create_user/",
        {
            "username": "testuser",
            "password": "testpassword",
            "firstname": "Test",
            "lastname": "User",
            "is_backoffice_user": is_backoffice_user,
        },
        follow=True,
    )
    assert response.status_code == 200
    assert User.objects.count() == count + 1
    assert User.objects.last().is_backoffice_user == is_backoffice_user


@pytest.mark.django_db
def test_backoffice_can_reset_regular_password(backoffice_client):
    user = user_factory()
    response = backoffice_client.post(
        "/backoffice/users/reset_password/{}/".format(user.pk),
        {"password1": "testpassword12", "password2": "testpassword12"},
        follow=True,
    )
    assert response.status_code == 200
    assert authenticate(username=user.username, password="testpassword12")


@pytest.mark.django_db
def test_backoffice_cannot_reset_regular_password_incorrect_repetition(
    backoffice_client
):
    user = user_factory()
    assert not authenticate(username=user.username, password="testpassword12")
    response = backoffice_client.post(
        "/backoffice/users/reset_password/{}/".format(user.pk),
        {"password1": "testpassword12", "password2": "testpassword1"},
        follow=True,
    )
    assert response.status_code == 200
    assert not authenticate(username=user.username, password="testpassword12")


@pytest.mark.django_db
def test_backoffice_cannot_reset_password_on_superuser(backoffice_client):
    user = user_factory(superuser=True)
    response = backoffice_client.post(
        "/backoffice/users/reset_password/{}/".format(user.pk),
        {"password1": "testpassword12", "password2": "testpassword1"},
        follow=True,
    )
    assert response.status_code == 200
    assert not authenticate(username=user.username, password="testpassword12")
