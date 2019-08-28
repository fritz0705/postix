import pytest

from postix.backoffice.checks import CheckError, check_quotas, check_tax_rates
from postix.core.models import ListConstraintProduct

from ..factories import list_constraint_factory, product_factory, quota_factory


@pytest.mark.django_db
def test_backoffice_quota_check():
    product_without_quota = product_factory()
    quota = quota_factory()
    product = product_factory()
    product.quota_set.add(quota)
    product.save()

    with pytest.raises(CheckError) as error_info:
        check_quotas()

    assert product_without_quota.name in str(error_info.value)
    assert product.name not in str(error_info.value)


@pytest.mark.django_db
def test_backoffice_tax_rate_check():
    product_factory()
    list_constraint_factory(price="10.00", product=product_factory())
    ListConstraintProduct.objects.update(tax_rate=7)

    with pytest.raises(CheckError) as error_info:
        check_tax_rates()

    assert "7" in str(error_info.value)
