import pytest

from ..factories import user_factory


@pytest.mark.django_db
def test_troubleshooter_login(client):
    user = user_factory(password="trololol123", troubleshooter=True)
    response = client.post(
        "/troubleshooter/login/",
        {"username": user.username, "password": "trololol123"},
        follow=True,
    )
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/troubleshooter/"


@pytest.mark.django_db
def test_troubleshooter_login_with_redirect(client, event_settings):
    user = user_factory(password="trololol123", troubleshooter=True)
    response = client.post(
        "/troubleshooter/login/?next=/troubleshooter/ping/",
        {"username": user.username, "password": "trololol123"},
        follow=True,
    )
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/troubleshooter/ping/"


@pytest.mark.django_db
def test_troubleshooter_login_incorrect_password(client):
    user = user_factory(password="trololol123", troubleshooter=True)
    response = client.post(
        "/troubleshooter/login/",
        {"username": user.username, "password": "trololol"},
        follow=True,
    )
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/troubleshooter/login/"


@pytest.mark.django_db
def test_troubleshooter_login_no_troubleshooter_user(client):
    user = user_factory(password="trololol123")
    response = client.post(
        "/troubleshooter/login/",
        {"username": user.username, "password": "trololol123"},
        follow=True,
    )
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/troubleshooter/login/"


@pytest.mark.django_db
def test_troubleshooter_logout(troubleshooter_client):
    response = troubleshooter_client.post("/troubleshooter/logout/", follow=True)
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/troubleshooter/login/"
