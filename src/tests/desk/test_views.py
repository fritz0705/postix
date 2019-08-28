import pytest

from ..factories import cashdesk_factory, cashdesk_session_before_factory, user_factory


@pytest.mark.django_db
def test_cashdesk_login_with_session(client):
    user = user_factory(password="trololol123")
    cashdesk_session_before_factory(ip="127.0.0.1", user=user)
    response = client.post(
        "/login/", {"username": user.username, "password": "trololol123"}, follow=True
    )
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/"
    assert "CHECKOUT" in response.content.decode()


@pytest.mark.django_db
def test_cashdesk_login_with_session_already_logged_in(client):
    user = user_factory(password="trololol123")
    cashdesk_session_before_factory(ip="127.0.0.1", user=user)
    client.force_login(user)
    response = client.get("/login/", follow=True)
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/"
    assert "CHECKOUT" in response.content.decode()


@pytest.mark.django_db
def test_cashdesk_login_with_session_without_start(client):
    user = user_factory(password="trololol123")
    session = cashdesk_session_before_factory(ip="127.0.0.1", user=user)
    session.start = None
    session.save
    client.force_login(user)
    response = client.get("/login/", follow=True)
    assert response.status_code == 200
    assert "CHECKOUT" in response.content.decode()
    session.refresh_from_db()
    assert session.start


@pytest.mark.django_db
def test_cashdesk_logged_in_without_active_session(client):
    user = user_factory(password="trololol123")
    client.force_login(user)
    response = client.get("/", follow=True)
    assert response.status_code == 200
    assert "You do not have an active session" in response.content.decode()


@pytest.mark.django_db
def test_cashdesk_login_without_active_session(client):
    user = user_factory(password="trololol123")
    cashdesk_factory(ip="127.0.0.1")
    response = client.post(
        "/login/", {"username": user.username, "password": "trololol123"}, follow=True
    )
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/login/"
    assert "You do not have an active session" in response.content.decode()


@pytest.mark.django_db
def test_cashdesk_login_with_session_wrong_device(client):
    user = user_factory(password="trololol123")
    cashdesk_session_before_factory(ip="10.0.0.2", user=user)
    response = client.post(
        "/login/", {"username": user.username, "password": "trololol123"}, follow=True
    )
    assert response.status_code == 200
    assert "not a registered cashdesk" in response.content.decode()


@pytest.mark.django_db
def test_cashdesk_login_inactive_user(client):
    user = user_factory(password="trololol123")
    cashdesk_session_before_factory(ip="127.0.0.1", user=user)
    user.is_active = False
    user.save()
    response = client.post(
        "/login/", {"username": user.username, "password": "trololol123"}, follow=True
    )
    assert response.status_code == 200
    assert (
        "No user account matches the entered credentials" in response.content.decode()
    )


@pytest.mark.django_db
def test_cashdesk_login_incorrect_credentials(client):
    user = user_factory(password="trololol123")
    cashdesk_session_before_factory(ip="127.0.0.1", user=user)
    response = client.post(
        "/login/",
        {"username": user.username, "password": "trololol123456789"},
        follow=True,
    )
    assert response.status_code == 200
    assert (
        "No user account matches the entered credentials" in response.content.decode()
    )


@pytest.mark.django_db
def test_cashdesk_login_with_session_wrong_desk(client):
    user = user_factory(password="trololol123")
    cashdesk_factory(ip="127.0.0.1")
    cashdesk_session_before_factory(ip="10.0.0.2", user=user)
    response = client.post(
        "/login/", {"username": user.username, "password": "trololol123"}, follow=True
    )
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/login/"
    assert "different cashdesk. Please go to" in response.content.decode()


@pytest.mark.django_db
def test_cashdesk_logout_after_session(client):
    user = user_factory(password="trololol123")
    session = cashdesk_session_before_factory(ip="127.0.0.1", user=user)
    assert not session.end
    client.force_login(user)
    response = client.post("/logout/", follow=True)
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/login/"


@pytest.mark.django_db
def test_cashdesk_logout_without_session(client):
    response = client.post("/logout/", follow=True)
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == "/login/"
