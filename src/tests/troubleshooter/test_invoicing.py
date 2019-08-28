import pytest

from postix.troubleshooter.invoicing import generate_invoice

from ..factories import transaction_position_factory


@pytest.mark.django_db
def test_invoicing(event_settings):
    transaction = transaction_position_factory().transaction
    transaction.receipt_id = 12345
    transaction.save()
    path = generate_invoice(transaction, address="Foo\nBar\nBaz")
    transaction.refresh_from_db()
    assert transaction.has_invoice, path
    assert generate_invoice(transaction, address="Foo\nBar\nBaz") == path
