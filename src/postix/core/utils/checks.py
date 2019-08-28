from postix.core.models import (
    ListConstraintEntry,
    PreorderPosition,
    TransactionPosition,
)


def is_redeemed(obj) -> bool:

    positive_types = ["redeem"]
    if isinstance(obj, ListConstraintEntry):
        positions = TransactionPosition.objects.filter(listentry=obj)
        positive_types.append("sell")
    elif isinstance(obj, PreorderPosition):
        positions = TransactionPosition.objects.filter(preorder_position=obj)
    else:  # noqa
        raise TypeError("Expected ListConstraintEntry or PreorderPosition object.")

    positives = positions.filter(type__in=positive_types)
    negatives = positions.filter(type="reverse")

    if positives.exists():
        return positives.count() > negatives.count()

    return False
