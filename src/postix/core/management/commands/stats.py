from django.core.management.base import BaseCommand
from django.db.models import Count

from postix.core.models import TransactionPosition


class Command(BaseCommand):
    help = "Print basic stats"

    def handle(self, *args, **kwargs):
        total = 0
        agg = (
            TransactionPosition.objects.order_by("product")
            .values("product__name", "product__price")
            .annotate(total=Count("id"), reverses=Count("reverses"))
        )

        for line in agg:
            count = line["total"] - line["reverses"]
            self.stdout.write(
                "{line[product__name]:30} {line[product__price]:>20} EUR       {count}".format(
                    line=line, count=count
                )
            )
            if "ticket" in line["product__name"]:
                total += count

        self.stdout.write(
            self.style.SUCCESS("Total tickets: {total}".format(total=total))
        )
