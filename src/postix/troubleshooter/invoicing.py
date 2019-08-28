from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.timezone import now
from django.utils.translation import ugettext as _
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from postix.core.models import EventSettings, Transaction
from postix.core.utils.pdf import (
    FONTSIZE,
    get_default_document,
    get_paragraph_style,
    money,
)


def generate_invoice(transaction: Transaction, address: str) -> str:
    if transaction.has_invoice:
        return transaction.get_invoice_path()

    _buffer = BytesIO()
    settings = EventSettings.get_solo()
    doc = get_default_document(_buffer, footer=settings.invoice_footer)
    style = get_paragraph_style()

    # Header
    our_address = settings.invoice_address.replace("\n", "<br />")
    our_address = Paragraph(our_address, style["Normal"])
    our_title = Paragraph(_("Invoice from"), style["Heading5"])

    their_address = address.replace("\n", "<br />")
    their_address = Paragraph(their_address, style["Normal"])
    their_title = Paragraph(_("Invoice to"), style["Heading5"])

    data = [[their_title, "", our_title], [their_address, "", our_address]]
    header = Table(
        data=data,
        colWidths=[doc.width * 0.3, doc.width * 0.3, doc.width * 0.4],
        style=TableStyle(
            [("FONTSIZE", (0, 0), (2, 1), FONTSIZE), ("VALIGN", (0, 0), (2, 1), "TOP")]
        ),
    )
    date = Table(
        data=[[now().strftime("%Y-%m-%d")]],
        colWidths=[doc.width],
        style=TableStyle([("ALIGN", (0, 0), (0, 0), "RIGHT")]),
    )
    invoice_title = Paragraph(
        _("Invoice for receipt {}").format(transaction.receipt_id), style["Heading1"]
    )

    data = [[_("Product"), _("Tax rate"), _("Net"), _("Gross")]]
    total_tax = 0
    for position in transaction.positions.all():
        total_tax += position.tax_value
        data.append(
            [
                position.product.name,
                "{} %".format(position.tax_rate),
                money(position.value - position.tax_value),
                money(position.value),
            ]
        )
    data.append([_("Included taxes"), "", "", money(total_tax)])
    data.append([_("Invoice total"), "", "", money(transaction.value)])
    last_row = len(data) - 1

    transaction_table = Table(
        data=data,
        colWidths=[doc.width * 0.5] + [doc.width * 0.5 / 3] * 3,
        style=TableStyle(
            [
                ("FONTSIZE", (0, 0), (3, last_row), FONTSIZE),
                # TODO: register bold font and use here: ('FACE', (0,0), (3,0), 'boldfontname'),
                ("ALIGN", (0, 0), (1, last_row), "LEFT"),
                ("ALIGN", (2, 0), (3, last_row), "RIGHT"),
                ("LINEABOVE", (0, 1), (3, 1), 1.0, colors.black),
                ("LINEABOVE", (3, last_row - 1), (3, last_row - 1), 1.0, colors.black),
                ("LINEABOVE", (3, last_row), (3, last_row), 1.2, colors.black),
            ]
        ),
    )
    disclaimer_text = _("This invoice is only valid with receipt #{}.").format(
        transaction.receipt_id
    )
    disclaimer_text += _("The invoice total has already been paid.")
    disclaimer = Paragraph(disclaimer_text, style["Normal"])

    story = [
        header,
        Spacer(1, 15 * mm),
        date,
        invoice_title,
        Spacer(1, 25 * mm),
        transaction_table,
        Spacer(1, 25 * mm),
        disclaimer,
    ]
    doc.build(story)
    _buffer.seek(0)
    stored_name = default_storage.save(
        transaction.get_invoice_path(allow_nonexistent=True),
        ContentFile(_buffer.read()),
    )
    return stored_name
