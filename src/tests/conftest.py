import pytest

from postix.core.models import EventSettings


@pytest.fixture
def event_settings():
    settings = EventSettings.get_solo()
    settings.invoice_address = "Foo Conferences\n42 Bar St\nBaz City"
    settings.initialized = True
    settings.save()
    return settings


@pytest.fixture
def troubleshooter_client(client):
    from .factories import user_factory

    user = user_factory(troubleshooter=True)
    client.force_login(user)
    return client


@pytest.fixture
def backoffice_client(client):
    from .factories import user_factory

    user = user_factory(backoffice=True)
    client.force_login(user)
    return client


@pytest.fixture
def superuser_client(client):
    from .factories import user_factory

    user = user_factory(superuser=True)
    client.force_login(user)
    return client


@pytest.fixture
def normal_pretix_data():
    return {
        "event": {
            "categories": [{"name": "Tickets", "id": 15}],
            "organizer": {"slug": "orga", "name": "Orga"},
            "orders": [
                {
                    "user": "user1@gmail.com",
                    "total": "100.00",
                    "status": "p",
                    "datetime": "2017-12-17T13:37:27Z",
                    "positions": [
                        {
                            "attendee_email": None,
                            "price": "100.00",
                            "item": 232,
                            "answers": [
                                {"answer": "Cool", "question": 10},
                                {"answer": "31", "question": 11},
                            ],
                            "secret": "xxxx",
                            "attendee_name": "User One",
                            "addon_to": None,
                            "id": 37950,
                            "variation": None,
                        }
                    ],
                    "code": "DQFEF",
                    "fees": [],
                },
                {
                    "user": "user2@hotmail.de",
                    "total": "100.00",
                    "status": "n",
                    "datetime": "2017-12-16T14:51:51Z",
                    "positions": [
                        {
                            "attendee_email": None,
                            "price": "100.00",
                            "item": 232,
                            "answers": [],
                            "secret": "yyyy",
                            "attendee_name": "User Two",
                            "addon_to": None,
                            "id": 37836,
                            "variation": None,
                        },
                        {
                            "attendee_email": None,
                            "price": "100.00",
                            "item": 232,
                            "answers": [],
                            "secret": "zzzz",
                            "attendee_name": "User Three",
                            "addon_to": None,
                            "id": 37837,
                            "variation": None,
                        },
                    ],
                    "code": "9SAR3",
                    "fees": [],
                },
            ],
            "questions": [
                {"question": "How do you like chocolate?", "type": "S", "id": 10},
                {"question": "How old are you?", "type": "S", "id": 11},
            ],
            "items": [
                {
                    "tax_rate": "19.00",
                    "category": 15,
                    "price": "100.00",
                    "active": True,
                    "admission": True,
                    "name": "Standard ticket",
                    "variations": [],
                    "id": 232,
                    "tax_name": "VAT",
                }
            ],
            "quotas": [{"items": [232], "variations": [], "size": 100, "id": 36}],
            "slug": "conf",
            "name": "Conference",
        }
    }
