import json
from io import BytesIO
from tempfile import TemporaryFile

import qrcode
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle

from postix.core.models import CashdeskSession, EventSettings, Record
from postix.core.utils.pdf import (
    FONTSIZE,
    get_default_document,
    get_paragraph_style,
    money,
    scale_image,
)


def get_qr_image(record) -> TemporaryFile:
    # TODO: check qr code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    data = "{date}\t{time}\t{direction}\t{amount}\t{entity}\t{entity_detail}\t{supervisor}\t{user}".format(
        **record.export_data
    )
    qr.add_data(data)
    qr.make()

    f = TemporaryFile()
    img = qr.make_image()
    img.save(f)
    return f


def get_session_header(session, doc, title="Kassenbericht"):
    style = get_paragraph_style()
    settings = EventSettings.get_solo()
    title_str = "[{}] {}".format(settings.short_name, title)
    title = Paragraph(title_str, style["Heading1"])
    tz = timezone.get_current_timezone()
    text = "{} an ".format(session.user.get_full_name() if session.user else "")
    text += "{cashdesk} (#{pk})<br/>{start} – {end}".format(
        cashdesk=session.cashdesk,
        pk=session.pk,
        start=session.start.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S"),
        end=session.end.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S"),
    )
    info = Paragraph(text, style["Normal"])

    return Table(
        data=[[[title, info], ""]],
        colWidths=[doc.width / 2] * 2,
        style=TableStyle(
            [
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("VALIGN", (0, 0), (1, 0), "TOP"),
            ]
        ),
    )


def get_signature_block(names, doc):
    col_width = (doc.width - 35) / 2
    second_sig = 2 if names[1] else 0
    return Table(
        data=[[names[0], "", names[1]]],
        colWidths=[col_width, 35, col_width],
        style=TableStyle(
            [
                ("FONTSIZE", (0, 0), (2, 0), FONTSIZE),
                ("LINEABOVE", (0, 0), (0, 0), 1.2, colors.black),
                ("LINEABOVE", (second_sig, 0), (second_sig, 0), 1.2, colors.black),
                ("VALIGN", (0, 0), (2, 0), "TOP"),
            ]
        ),
    )


def generate_item_report(session: CashdeskSession, doc) -> str:
    """
    Generates a closing report for a CashdeskSession that handled items
    """
    if not session.end:
        return

    style = get_paragraph_style()

    header = get_session_header(session, doc)

    # Sales table
    sales_heading = Paragraph("Tickets", style["Heading3"])
    data = [["Ticket", "Einzelpreis", "Presale", "Verkauf", "Stornos", "Gesamt"]]
    sales_raw_data = session.get_product_sales()
    sales = [
        [
            Paragraph(p["product"].name, style["Normal"]),
            Paragraph(money(p["value_single"]), style["Right"]),
            Paragraph(str(p["presales"]), style["Right"]),
            Paragraph(str(p["sales"]), style["Right"]),
            Paragraph(str(p["reversals"]), style["Right"]),
            Paragraph(money(p["value_total"]), style["Right"]),
        ]
        for p in sales_raw_data
    ]
    data += sales
    data += [
        ["", "", "", "", "", money(sum([p["value_total"] for p in sales_raw_data]))]
    ]
    last_row = len(data) - 1
    sales = Table(
        data=data,
        colWidths=[120] + [(doc.width - 120) / 5] * 5,
        style=TableStyle(
            [
                ("FONTSIZE", (0, 0), (5, last_row), FONTSIZE),
                # TODO: register bold font and use here: ('FACE', (0,0), (3,0), 'boldfontname'),
                ("ALIGN", (0, 0), (0, last_row), "LEFT"),
                ("ALIGN", (1, 0), (5, last_row), "RIGHT"),
                ("LINEABOVE", (0, 1), (5, 1), 1.0, colors.black),
                ("LINEABOVE", (5, last_row), (5, last_row), 1.2, colors.black),
            ]
        ),
    )

    # Items table
    items_heading = Paragraph("Auszählung", style["Heading3"])
    data = [["", "Einzählung", "Umsatz", "Auszählung", "Differenz"]]

    # geld immer decimal mit € und nachkommastellen
    cash_transactions = session.get_cash_transaction_total()
    cash = [
        [
            "Bargeld",
            money(session.cash_before),
            money(cash_transactions),
            money(session.cash_after),
            money(session.cash_before + cash_transactions - session.cash_after),
        ]
    ]
    items = [
        [
            d["item"].name,
            d["movements"],
            d["transactions"],
            abs(d["final_movements"]),
            d["total"],
        ]
        for d in session.get_current_items()
    ]
    last_row = len(items) + 1
    items = Table(
        data=data + cash + items,
        colWidths=[120] + [(doc.width - 120) / 4] * 4,
        style=TableStyle(
            [
                ("FONTSIZE", (0, 0), (4, last_row), FONTSIZE),
                # TODO: register bold font and use here: ('FACE', (0,0), (3,0), 'boldfontname'),
                ("ALIGN", (0, 0), (0, last_row), "LEFT"),
                ("ALIGN", (1, 0), (4, last_row), "RIGHT"),
                ("LINEABOVE", (0, 1), (4, 1), 1.0, colors.black),
            ]
        ),
    )

    # Signatures
    signatures = get_signature_block(
        [
            "Kassierer/in: {}".format(
                session.user.get_full_name() if session.user else ""
            ),
            "Ausgezählt durch {}".format(session.backoffice_user_after.get_full_name()),
        ],
        doc=doc,
    )

    return [
        header,
        Spacer(1, 15 * mm),
        sales_heading,
        sales,
        Spacer(1, 10 * mm),
        items_heading,
        items,
        Spacer(1, 30 * mm),
        signatures,
    ]


def generate_session_closing(record, doc):
    session = record.cash_movement.session
    tz = timezone.get_current_timezone()
    header = get_session_header(session, doc=doc, title="Umsatzermittlung")
    data = [
        ["Datum", "Grund", "Betrag"],
        [
            session.start.astimezone(tz).strftime("%Y-%m-%d, %H:%M:%S"),
            "Anfangsbestand",
            money(0),
        ],
    ]
    running_total = 0
    for movement in session.cash_movements.all():
        running_total += movement.cash
        data.append(
            [
                movement.timestamp.astimezone(tz).strftime("%Y-%m-%d, %H:%M:%S"),
                "Wechselgeld" if movement.cash > 0 else "Abschöpfung",
                money(movement.cash),
            ]
        )
    data.append(
        [
            session.end.astimezone(tz).strftime("%Y-%m-%d, %H:%M:%S"),
            "Endbestand",
            money(0),
        ]
    )
    data.append(["", "Umsatz", money(-running_total)])
    last_row = len(data) - 1
    transactions = Table(
        data=data,
        colWidths=[doc.width / 3] * 3,
        style=TableStyle(
            [
                ("FONTSIZE", (0, 0), (2, last_row), FONTSIZE),
                ("ALIGN", (0, 0), (0, last_row), "LEFT"),
                ("ALIGN", (1, 0), (2, last_row), "RIGHT"),
                ("LINEABOVE", (0, 1), (2, 1), 1.0, colors.black),
                ("LINEABOVE", (1, last_row), (2, last_row), 1.2, colors.black),
            ]
        ),
    )
    return [
        header,
        Spacer(1, 15 * mm),
        transactions,
        Spacer(1, 30 * mm),
        get_signature_block(
            [
                "Abgeschlossen durch: {}".format(
                    record.backoffice_user.get_full_name()
                ),
                "",
            ],
            doc=doc,
        ),
    ]


def generate_balance_statement(record, doc):
    data = json.loads(record.data)
    style = get_paragraph_style()
    settings = EventSettings.get_solo()
    title_str = "[{}] Kassenabschluss".format(settings.short_name)
    title = Paragraph(title_str, style["Heading1"])
    tz = timezone.get_current_timezone()
    text = record.datetime.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
    info = Paragraph(text, style["Normal"])

    header = Table(
        data=[[[title, info], ""]],
        colWidths=[doc.width / 2] * 2,
        style=TableStyle(
            [
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("VALIGN", (0, 0), (1, 0), "TOP"),
            ]
        ),
    )

    bills = [5, 10, 20, 50, 100, 200, 500]
    bills_data = [["Wert", "Manuell", "Maschinell", "In Bündeln"]]
    for bill in bills:
        bills_data.append(
            [
                money(bill),
                data["bills_manually"].get("bill_{}".format(bill), 0),
                data["bills_automated"].get("bill_{}".format(bill), 0),
                data["bills_bulk"].get("bill_{}00".format(bill), 0) * 100,
            ]
        )
    bills_data.append(
        [
            "",
            money(data["bills_manually"]["total"]),
            money(data["bills_automated"]["total"]),
            money(data["bills_bulk"]["total"]),
        ]
    )

    coins = [
        (0.01, 50),
        (0.02, 100),
        (0.05, 250),
        (0.10, 400),
        (0.20, 800),
        (0.50, 2000),
        (1, 2500),
        (2, 5000),
    ]
    coins_data = [["Wert", "Maschinell", "In Rollen"]]
    for coin in coins:
        coins_data.append(
            [
                money(coin[0]),
                data["coins_automated"].get("coin_{}".format(int(coin[0] * 100)), 0),
                int(
                    data["coins_bulk"].get("coin_{}".format(coin[1]), 0)
                    * (coin[1] / (coin[0] * 100))
                ),
            ]
        )
    coins_data.append(
        [
            "",
            money(data["coins_automated"]["total"]),
            money(data["coins_bulk"]["total"]),
        ]
    )

    last_row = len(bills_data) - 1
    bills_table = Table(
        data=bills_data,
        colWidths=[doc.width / 4] * 4,
        style=TableStyle(
            [
                ("FONTSIZE", (0, 0), (2, last_row), FONTSIZE),
                ("ALIGN", (0, 0), (3, last_row), "RIGHT"),
                ("LINEABOVE", (0, 1), (3, 1), 1.0, colors.black),
                ("LINEABOVE", (1, last_row), (3, last_row), 1.2, colors.black),
            ]
        ),
    )
    last_row = len(coins_data) - 1
    coins_table = Table(
        data=coins_data,
        colWidths=[doc.width / 3] * 3,
        style=TableStyle(
            [
                ("FONTSIZE", (0, 0), (2, last_row), FONTSIZE),
                ("ALIGN", (0, 0), (2, last_row), "RIGHT"),
                ("LINEABOVE", (0, 1), (2, 1), 1.0, colors.black),
                ("LINEABOVE", (1, last_row), (2, last_row), 1.2, colors.black),
            ]
        ),
    )
    final_table_data = [
        ["Erwartet:", money(data["expected"])],
        ["Ausgezählt:", money(data["total"])],
        ["Differenz:", money(record.amount)],
    ]
    last_row = len(final_table_data) - 1
    final_table = Table(
        data=final_table_data,
        colWidths=[doc.width / 4] * 2,
        style=TableStyle(
            [
                ("FONTSIZE", (0, 0), (1, last_row), FONTSIZE),
                ("ALIGN", (0, 0), (0, last_row), "LEFT"),
                ("ALIGN", (1, 0), (1, last_row), "RIGHT"),
            ]
        ),
    )
    return [
        header,
        Spacer(1, 15 * mm),
        bills_table,
        Spacer(1, 15 * mm),
        coins_table,
        Spacer(1, 15 * mm),
        final_table,
    ]


def generate_record(record: Record) -> str:
    """
    Generates the PDF for a given record; returns the path to the record PDF.
    """

    _buffer = BytesIO()
    settings = EventSettings.get_solo()
    doc = get_default_document(
        _buffer, footer=settings.report_footer + "\n{}".format(record.checksum or "")
    )
    style = get_paragraph_style()

    # Header: info text and qr code
    title_str = "[{}] ".format(settings.short_name)
    direction = "Von" if record.type == "inflow" else "Nach"
    if not record.pk:
        title_str += "Beleg"
        direction = "Von/Nach:"
    elif record.is_balancing:
        title_str += "Kassenabschluss"
    else:
        title_str += "Einnahme" if record.type == "inflow" else "Ausgabe"
    title = Paragraph(title_str, style["Heading1"])
    tz = timezone.get_current_timezone()
    datetime = record.datetime.astimezone(tz) if record.pk else ""
    logo = scale_image(get_qr_image(record), 100) if record.pk else ""
    header = Table(
        data=[[[title], logo]],
        colWidths=[doc.width / 2] * 2,
        style=TableStyle(
            [
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("VALIGN", (0, 0), (1, 0), "TOP"),
            ]
        ),
    )
    name = record.named_entity
    if record.cash_movement and record.cash_movement.session:
        name += " (#{})".format(record.cash_movement.session.pk)
    info = [
        ["Datum", datetime.strftime("%Y-%m-%d, %H:%M:%S") if record.pk else ""],
        [direction, name or ""],
        ["Betrag", money(record.amount) if record.pk else ""],
    ]
    info = [
        [
            Paragraph("<b>{}</b>".format(line[0]), style["Normal"]),
            Paragraph(line[1], style["Normal"]),
        ]
        for line in info
    ]

    info_table = Table(
        data=info,
        colWidths=[90, doc.width - 90],
        style=TableStyle([("ALIGN", (0, 0), (0, 0), "RIGHT")]),
    )

    # Signatures
    signature1 = get_signature_block(
        [
            "Bearbeiter/in: {}".format(
                record.backoffice_user.get_full_name() if record.pk else ""
            ),
            "",
        ],
        doc=doc,
    )

    story = [header, Spacer(1, 15 * mm), info_table, Spacer(1, 40 * mm), signature1]
    if record.named_carrier:
        story.append(Spacer(1, 40 * mm))
        story.append(
            get_signature_block(
                [
                    "{}: {}".format(
                        "Einlieferer/in" if record.type == "inflow" else "Empfänger/in",
                        record.named_carrier,
                    ),
                    "",
                ],
                doc=doc,
            )
        )
    if record.cash_movement and record.closes_session:
        if record.cash_movement.session.cashdesk.handles_items:
            story.append(PageBreak())
            story += generate_item_report(record.cash_movement.session, doc=doc)
        story.append(PageBreak())
        story += generate_session_closing(record, doc=doc)
    if record.is_balancing:
        story.append(PageBreak())
        story += generate_balance_statement(record, doc=doc)

    doc.build(story)
    _buffer.seek(0)
    if not record.pk:
        return _buffer
    stored_name = default_storage.save(
        record.get_new_record_path(), ContentFile(_buffer.read())
    )
    return stored_name
