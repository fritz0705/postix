import csv

from django.core.management.base import BaseCommand
from django.db import transaction

from postix.core.models import ListConstraint, ListConstraintEntry


class Command(BaseCommand):
    help = "Invocation: import_member ~/member_list.csv [BLN]"

    def add_arguments(self, parser):
        parser.add_argument("member_list")
        parser.add_argument("--prefix")

    def handle(self, *args, **kwargs):
        constraints, _ = ListConstraint.objects.get_or_create(
            confidential=True, name="Mitglieder"
        )
        import_count = import_known = 0
        local_prefix = kwargs.get("prefix")
        entries = {e.identifier: e for e in constraints.entries.all()}
        to_create = []

        with open(kwargs["member_list"], "r") as member_list:
            if not local_prefix:
                reader = csv.DictReader(member_list, delimiter="\t")
            else:
                reader = csv.DictReader(member_list, delimiter=";")
            with transaction.atomic():
                for row in reader:
                    if not any(row.values()):
                        continue  # empty line

                    if local_prefix:
                        identifier = "{}-{}".format(local_prefix, row["CHAOSNR"])
                        name = row["NAME"].strip()
                    else:
                        identifier = row.get("CHAOSNR") or row.get("chaos_number", "")
                        name = "{} {}".format(
                            row.get("VORNAME", "") or row.get("first_name", ""),
                            row.get("NACHNAME", "") or row.get("last_name", ""),
                        )

                    if "state" in row and row.get("state") != "bezahlt":
                        # Ignore or remove unpaid member
                        if identifier in entries:
                            le = entries.get(identifier)
                            if (
                                not le.positions.exists()
                            ):  # If positions exist, the person already got in, cannot remove, we don't care
                                le.delete()
                        continue

                    if identifier in entries:
                        import_known += 1
                        le = entries[identifier]
                        if le.name != name:
                            le.name = name
                            le.save()
                    else:
                        import_count += 1
                        le = ListConstraintEntry(
                            identifier=identifier, list=constraints, name=name
                        )
                        entries[identifier] = le
                        to_create.append(le)

                ListConstraintEntry.objects.bulk_create(to_create)
        self.stdout.write(
            self.style.SUCCESS(
                "Imported {} entries of the dataset, {} were already known."
            ).format(import_count, import_known)
        )
