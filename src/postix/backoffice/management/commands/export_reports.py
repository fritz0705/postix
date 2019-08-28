import os
import shutil

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from postix.backoffice.report import generate_record
from postix.core.models import Record


class Command(BaseCommand):
    help = "Creates a directory called `export-yyyy-mm-dd-hhmmss` and collects copies of every session's most recent record."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true", help="Generate missing documents"
        )

    def handle(self, *args, **options):
        export_dir = os.path.join(
            ".", "export-{}".format(now().strftime("%Y-%m-%d-%H%M%S"))
        )
        os.mkdir(export_dir)
        successful_exports = 0
        failed_exports = []
        force = options["force"]

        for record in Record.objects.all():
            report_path = record.record_path
            if not report_path and force:
                generate_record(record)
                report_path = record.record_path
            if report_path:
                shutil.copy2(report_path, export_dir)
                successful_exports += 1
            else:
                failed_exports.append(record.pk)

        success_msg = "Exported {} records to directory {}.".format(
            successful_exports, export_dir
        )
        self.stdout.write(self.style.SUCCESS(success_msg))

        if failed_exports:
            warn_msg = "Could not find files for {} records (IDs: {}). Use --force to generate them.".format(
                len(failed_exports), failed_exports
            )
            self.stdout.write(self.style.WARNING(warn_msg))
