import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from postix.core.models import Cashdesk, Item, Preorder, PreorderPosition, Product

from ..factories import item_factory, product_factory, user_factory


@pytest.mark.parametrize(
    "url,expected",
    (
        ("/backoffice/", 302),
        ("/backoffice/session/new/", 200),
        ("/backoffice/session/", 200),
        ("/backoffice/reports/", 200),
        ("/backoffice/create_user/", 200),
        ("/backoffice/users/", 200),
        ("/backoffice/wizard/users/", 302),
        ("/backoffice/wizard/settings/", 302),
        ("/backoffice/wizard/cashdesks/", 302),
        ("/backoffice/wizard/import/", 302),
        ("/backoffice/wizard/items/", 302),
        ("/backoffice/wizard/items/new", 302),
    ),
)
@pytest.mark.django_db
def test_can_access_pages(backoffice_client, url, expected):
    response = backoffice_client.get(url)
    assert response.status_code == expected
    if expected == 200:
        assert (
            "Please call a superuser to initialize this event's settings."
            in response.content.decode()
        )


@pytest.mark.django_db
def test_wizard_settings_view(superuser_client, event_settings):
    response = superuser_client.get("/backoffice/wizard/settings/")
    assert response.status_code == 200
    response = superuser_client.post(
        "/backoffice/wizard/settings/",
        {
            "name": "Chaos+Communication+Congress",
            "short_name": "c3",
            "support_contact": "rixx & rami",
            "invoice_address": "An Address",
            "invoice_footer": "Woohoo an invoice",
            "receipt_address": "Yet another address",
            "receipt_footer": "Another footer",
            "report_footer": "Yet Another footer",
            "initialized": True,
        },
        follow=True,
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_wizard_create_cashdesks(superuser_client, event_settings):
    assert Cashdesk.objects.count() == 0
    response = superuser_client.get("/backoffice/wizard/cashdesks/new")
    assert response.status_code == 200
    response = superuser_client.post(
        "/backoffice/wizard/cashdesks/new",
        {
            "name": "Cashdesk 1",
            "ip_address": "10.0.0.1",
            "printer_queue_name": "printer1",
        },
        follow=True,
    )
    assert response.status_code == 200
    assert Cashdesk.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("role", ("troubleshooter", "backoffice", "superuser"))
@pytest.mark.parametrize("direction", ("y", "n"))
def test_wizard_change_user_rights(superuser_client, event_settings, role, direction):
    if direction == "y":
        user = user_factory()
    else:
        user = user_factory(superuser=True, backoffice=True, troubleshooter=True)
    attr = "is_{}".format(role)
    if role == "backoffice":
        attr += "_user"
    assert getattr(user, attr) == (not direction == "y")

    response = superuser_client.post(
        "/backoffice/wizard/users/",
        {"target": "{}-{}".format(role, direction), "user": user.pk},
        follow=True,
    )
    assert response.status_code == 200
    user.refresh_from_db()

    if direction == "y":
        assert "User rights have been expanded" in response.content.decode()
    else:
        assert "User rights have been curtailed" in response.content.decode()
    assert getattr(user, attr) == (direction == "y")


@pytest.mark.django_db
def test_wizard_pretix_import(superuser_client, event_settings, normal_pretix_data):
    assert Product.objects.count() == 0
    assert Preorder.objects.count() == 0
    assert PreorderPosition.objects.count() == 0
    assert Cashdesk.objects.count() == 0
    f = SimpleUploadedFile("pretix.json", json.dumps(normal_pretix_data).encode())
    response = superuser_client.post(
        "/backoffice/wizard/import/",
        {"_file": f, "cashdesks": 5, "questions": "10"},
        follow=True,
    )
    assert response.status_code == 200
    assert Product.objects.count() == 1
    assert Preorder.objects.count() == 2
    assert PreorderPosition.objects.count() == 3
    assert Cashdesk.objects.count() == 5


@pytest.mark.django_db
def test_wizard_create_new_items(superuser_client, event_settings):
    assert Item.objects.count() == 0
    product = product_factory()
    response = superuser_client.post(
        "/backoffice/wizard/items/new",
        {
            "name": "Name",
            "description": "Description",
            "initial_stock": 50,
            "products": str(product.pk),
        },
        follow=True,
    )
    assert response.status_code == 200
    assert Item.objects.count() == 1


@pytest.mark.django_db
def test_wizard_edit_item(superuser_client, event_settings):
    item = item_factory()
    product = product_factory()
    response = superuser_client.post(
        "/backoffice/wizard/items/{}/".format(item.pk),
        {
            "name": "Name",
            "description": "Description",
            "initial_stock": 20,
            "products": str(product.pk),
        },
        follow=True,
    )
    assert response.status_code == 200
    old_name = item.name
    item.refresh_from_db()
    assert item.name != old_name
