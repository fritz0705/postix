import json
import tempfile
from decimal import Decimal

import pytest

from postix.core.models import Cashdesk, Preorder, PreorderPosition, Product
from postix.core.utils.pretix_import import import_pretix_data


@pytest.mark.django_db
def test_pretix_import_from_string(normal_pretix_data):
    import_pretix_data(
        json.dumps(normal_pretix_data), add_cashdesks=5, questions=["10"]
    )
    assert Product.objects.count() == 1
    assert Preorder.objects.count() == 2
    assert PreorderPosition.objects.count() == 3
    assert Cashdesk.objects.count() == 5


@pytest.mark.django_db
def test_pretix_import_from_file(normal_pretix_data):
    with tempfile.NamedTemporaryFile() as t:
        t.write(json.dumps(normal_pretix_data).encode())
        t.seek(0)
        import_pretix_data(t, add_cashdesks=5, questions="10")

    assert Product.objects.count() == 1
    assert Preorder.objects.count() == 2
    assert PreorderPosition.objects.count() == 3
    assert Cashdesk.objects.count() == 5


@pytest.mark.django_db
def test_pretix_import_regular(normal_pretix_data):
    assert Preorder.objects.count() == 0
    assert PreorderPosition.objects.count() == 0
    assert Cashdesk.objects.count() == 0
    assert Product.objects.count() == 0

    import_pretix_data(normal_pretix_data, add_cashdesks=5, questions=["10"])

    assert Product.objects.count() == 1
    assert Preorder.objects.count() == 2
    assert PreorderPosition.objects.count() == 3
    assert Cashdesk.objects.count() == 5

    product = Product.objects.first()
    assert product.name == "Standard ticket"
    assert product.price == Decimal("100.00")
    assert product.tax_rate == Decimal("19.00")

    assert PreorderPosition.objects.exclude(information="").count() == 1

    import_pretix_data(
        normal_pretix_data, questions=["10"]
    )  # import same data a second time

    assert Product.objects.count() == 1
    assert Preorder.objects.count() == 2
    assert PreorderPosition.objects.count() == 3
    assert Cashdesk.objects.count() == 5

    product = Product.objects.first()
    assert product.name == "Standard ticket"
    assert product.price == Decimal("100.00")
    assert product.tax_rate == Decimal("19.00")

    assert PreorderPosition.objects.exclude(information="").count() == 1

    normal_pretix_data["event"]["orders"][0]["status"] = "n"
    normal_pretix_data["event"]["orders"][1]["status"] = "p"
    normal_pretix_data["event"]["orders"][1]["positions"][0]["secret"] += "abc"

    import_pretix_data(
        normal_pretix_data, questions=["10"]
    )  # import same data a second time

    assert Product.objects.count() == 1
    assert Preorder.objects.count() == 2
    assert PreorderPosition.objects.count() == 3
