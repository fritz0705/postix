from django.core.management.base import BaseCommand

from postix.core.utils.pretix_import import import_pretix_data


class Command(BaseCommand):
    help = "Imports a pretix-style presale export, generating products and preorder positions."

    def add_arguments(self, parser):
        parser.add_argument("presale_json")
        parser.add_argument("--add-cashdesks", action="store_true", default=False)
        parser.add_argument("--questions")

    def handle(self, *args, **kwargs):
        try:
            with open(kwargs["presale_json"], "r") as user_data:
                import_pretix_data(
                    user_data,
                    add_cashdesks=kwargs.get("add_cashdesks"),
                    log=self.stdout,
                    style=self.style,
                    questions=kwargs.get("questions"),
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR("Failed to import file."))
            self.stdout.write(e)
            return
