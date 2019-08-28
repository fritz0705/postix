import pytest

from ..factories import user_factory


@pytest.mark.django_db
def test_backoffice_login(client):
    user = user_factory(password="trololol123", backoffice=True)
    response = client.post(
        "/backoffice/login/",
        {"username": user.username, "password": "trololol123"},
        follow=True,
    )
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/backoffice/session/"


@pytest.mark.django_db
def test_backoffice_login_with_redirect(client, event_settings):
    user = user_factory(password="trololol123", backoffice=True)
    response = client.post(
        "/backoffice/login/?next=/backoffice/session/new/",
        {"username": user.username, "password": "trololol123"},
        follow=True,
    )
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/backoffice/session/new/"


@pytest.mark.django_db
def test_backoffice_login_incorrect_password(client):
    user = user_factory(password="trololol123", backoffice=True)
    response = client.post(
        "/backoffice/login/",
        {"username": user.username, "password": "trololol"},
        follow=True,
    )
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/backoffice/login/"


@pytest.mark.django_db
def test_backoffice_login_no_backoffice_user(client):
    user = user_factory(password="trololol123")
    response = client.post(
        "/backoffice/login/",
        {"username": user.username, "password": "trololol123"},
        follow=True,
    )
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/backoffice/login/"


@pytest.mark.django_db
def test_backoffice_logout(backoffice_client):
    response = backoffice_client.post("/backoffice/logout/", follow=True)
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/backoffice/login/"


@pytest.mark.django_db
def test_backoffice_switch_user(backoffice_client):
    response = backoffice_client.post(
        "/backoffice/switch-user/?next=/backoffice/session/new/", follow=True
    )
    assert response.status_code == 200
    assert (
        response.redirect_chain[-1][0]
        == "/backoffice/login/?next=/backoffice/session/new/"
    )
