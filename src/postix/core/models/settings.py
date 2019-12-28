from django.db import models
from django.utils.translation import ugettext_lazy as _
from solo.models import SingletonModel

from postix.core.mixins import Exportable


class EventSettings(Exportable, SingletonModel):
    name = models.CharField(
        max_length=100, default="Generic Event", verbose_name=_("Name")
    )
    short_name = models.CharField(
        max_length=50,
        default="GE",
        verbose_name=_("Short name"),
        help_text=_("A short name for your event."),
    )
    support_contact = models.CharField(
        max_length=200,
        verbose_name=_("Support contact"),
        default=_(
            "Who is flying this thing? Enter your contact information as support contact info, please."
        ),
        help_text=_("Your - yes YOUR - real-time contact info, e.g. phone number."),
    )
    invoice_address = models.CharField(
        verbose_name=_("Invoice address"), max_length=200, blank=True, null=True
    )
    invoice_footer = models.CharField(
        verbose_name=_("Invoice footer"), max_length=200, blank=True, null=True
    )
    receipt_address = models.CharField(
        verbose_name=_("Receipt address"), max_length=200, blank=True, null=True
    )
    receipt_footer = models.CharField(
        verbose_name=_("Receipt footer"),
        max_length=200,
        default=_("Thank you!"),
        help_text=_(
            "Use this to display additional disclaimers/data not in your address, such as VAT IDs."
        ),
    )
    report_footer = models.CharField(
        verbose_name=_("Report footer"),
        max_length=500,
        default="CCC Veranstaltungsgesellschaft mbH",
        help_text=_("This will show up on backoffice session reports."),
    )
    initialized = models.BooleanField(default=False)
    queue_sync_url = models.URLField(
        verbose_name=_("c3queue.de URL"),
        max_length=100,
        help_text=_("The URL of the c3queue.de instance"),
        default="https://c3queue.de",
        null=True,
        blank=True,
    )
    queue_sync_token = models.CharField(
        max_length=100,
        verbose_name=_("c3queue authentication token"),
        null=True,
        blank=True,
    )
    maintenance_mode = models.BooleanField(
        default=False,
        verbose_name=_("Maintenance mode"),
        help_text=_(
            "Block everybody except for superuser users from using the server."
        ),
    )
    last_import_questions = models.TextField(
        verbose_name=_("Last input for imported questions"),
        null=False,
        blank=True,
        default="",
    )

    class Meta:
        verbose_name = "Event Settings"
