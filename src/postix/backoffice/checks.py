from decimal import Decimal

from django.utils.translation import ugettext as _

from postix.core.models import ListConstraintProduct, Product, WarningConstraintProduct

_check_registry = set()


def register_check(fn):
    _check_registry.add(fn)
    return fn


class CheckError(Exception):
    pass


@register_check
def check_quotas():
    prods = []
    for p in Product.objects.filter(is_visible=True).prefetch_related("quota_set"):
        quotas = bool(p.quota_set.all())
        if not quotas:
            prods.append(p)

    if prods:
        raise CheckError(
            _(
                "The following products are visible but have no quota: {products}".format(
                    products=", ".join(str(r) for r in prods)
                )
            )
        )


@register_check
def check_tax_rates():
    product_rates = set(
        Product.objects.exclude(price=0).values_list("tax_rate", flat=True).distinct()
    )
    constraint_rates = set(
        ListConstraintProduct.objects.filter(price__gt=0)
        .values_list("tax_rate", flat=True)
        .distinct()
    ) | set(
        WarningConstraintProduct.objects.filter(price__gt=0)
        .values_list("tax_rate", flat=True)
        .distinct()
    )
    if len(constraint_rates - product_rates):
        raise CheckError(
            _(
                "You have list or warning constraints with tax rates of {constraint_rates} "
                "but your products only use the tax rates {product_rates}. Are you sure this is "
                "correct?"
            ).format(
                constraint_rates=", ".join(str(r) + "%" for r in constraint_rates),
                product_rates=", ".join(str(r) + "%" for r in product_rates),
            )
        )
    if Decimal("0.00") in product_rates and len(product_rates) > 1:
        raise CheckError(
            _(
                "You have some products that use a non-zero tax rate but the following products are set to 0%: "
                "{products}"
            ).format(
                products=", ".join(str(p) for p in Product.objects.filter(tax_rate=0))
            )
        )


def all_errors():
    errors = []
    for check in _check_registry:
        try:
            check()
        except CheckError as e:
            errors.append(str(e))

    return errors
