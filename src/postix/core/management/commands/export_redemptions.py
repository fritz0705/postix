import json

from django.core.management.base import BaseCommand

from postix.core.models import TransactionPosition


class Command(BaseCommand):
    help = "Export preorder redemptions."

    def handle(self, *args, **kwargs):
        pos = TransactionPosition.objects.filter(
            reversed_by__isnull=True, preorder_position__isnull=False
        ).select_related("preorder_position", "transaction")
        self.stdout.write(
            json.dumps(
                [
                    {
                        "secret": p.preorder_position.secret,
                        "datetime": p.transaction.datetime.isoformat(),
                    }
                    for p in pos
                ]
            )
        )
