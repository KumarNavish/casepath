from __future__ import annotations

import os
import shutil
from pathlib import Path

import fitz
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parent / "artifacts"
SOURCE_DATE_EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "1786406400"))

INK = colors.HexColor("#1d1d1f")
MUTED = colors.HexColor("#666666")
LINE = colors.HexColor("#dedbd6")
LIGHT = colors.HexColor("#f5f4f2")

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="DocTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=INK,
        spaceAfter=12,
    )
)
styles.add(
    ParagraphStyle(
        name="DocSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=MUTED,
        spaceAfter=16,
    )
)
styles.add(
    ParagraphStyle(
        name="H1x",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=INK,
        spaceBefore=10,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="Bodyx",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=INK,
        spaceAfter=7,
    )
)
styles.add(
    ParagraphStyle(
        name="Smallx",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=MUTED,
        spaceAfter=4,
    )
)


def reset_output() -> None:
    retained_runtime_photos = {
        "bedroom-corner-2026-07-27.jpg",
        "window-corner-2026-08-08.jpg",
    }
    if ROOT.exists():
        for child in ROOT.iterdir():
            # The two checked-in photographs are independently curated source
            # evidence. Document regeneration must never delete them; the
            # build's photographic-evidence step separately verifies and
            # reproduces their exact runtime bytes from hash-pinned sources.
            if (
                child.is_file()
                and child.suffix.lower() in {".jpg", ".jpeg"}
                and child.name in retained_runtime_photos
            ):
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    ROOT.mkdir(parents=True, exist_ok=True)


def set_epoch(path: Path) -> None:
    os.utime(path, (SOURCE_DATE_EPOCH, SOURCE_DATE_EPOCH))


def invariant_canvas(*args, **kwargs) -> Canvas:
    kwargs["invariant"] = 1
    return Canvas(*args, **kwargs)


def footer(canvas: Canvas, document, reference: str) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(LINE)
    canvas.line(24 * mm, 15 * mm, width - 24 * mm, 15 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(24 * mm, 9 * mm, reference)
    canvas.drawRightString(width - 24 * mm, 9 * mm, f"Page {document.page}")
    canvas.restoreState()


def normalize_pdf_metadata(
    path: Path,
    *,
    title: str,
    author: str,
    subject: str,
    pdf_date: str,
) -> None:
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": title,
            "/Author": author,
            "/Subject": subject,
            "/Creator": "Document Services",
            "/Producer": "Document Services",
            "/CreationDate": pdf_date,
            "/ModDate": pdf_date,
        }
    )
    temporary = path.with_suffix(".normalized.pdf")
    with temporary.open("wb") as stream:
        writer.write(stream)
    os.replace(temporary, path)
    set_epoch(path)


def make_pdf(
    path: Path,
    *,
    title: str,
    subtitle: str,
    story: list,
    reference: str,
    author: str,
    subject: str,
    pdf_date: str,
) -> None:
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=24 * mm,
        rightMargin=24 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        title=title,
        author=author,
        subject=subject,
    )
    content = [Paragraph(title, styles["DocTitle"]), Paragraph(subtitle, styles["DocSub"]), *story]
    document.build(
        content,
        onFirstPage=lambda canvas, doc: footer(canvas, doc, reference),
        onLaterPages=lambda canvas, doc: footer(canvas, doc, reference),
        canvasmaker=invariant_canvas,
    )
    normalize_pdf_metadata(
        path,
        title=title,
        author=author,
        subject=subject,
        pdf_date=pdf_date,
    )


def styled_table(rows: list[list[str]], widths: list[float], *, header: bool = False) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("PADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    else:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (0, -1), LIGHT),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def lease() -> None:
    story: list = [Paragraph("1. Parties and premises", styles["H1x"])]
    story.extend(
        [
            styled_table(
                [
                    ["Landlord", "Rheinblick Immobilien AG, Clarastrasse 28, 4058 Basel"],
                    ["Tenant", "Alex Morgan, Feldbergstrasse 114, 4057 Basel"],
                    ["Premises", "3-room apartment, 3rd floor, Feldbergstrasse 114, 4057 Basel"],
                    ["Start date", "1 February 2024"],
                    ["Monthly net rent", "CHF 1,640"],
                    ["Advance ancillary costs", "CHF 240"],
                ],
                [40 * mm, 115 * mm],
            ),
            Spacer(1, 10),
            Paragraph(
                "The apartment is rented for residential use. The tenant may use the bedroom, "
                "living room, kitchen, bathroom, cellar compartment and shared laundry facilities "
                "in accordance with the building rules.",
                styles["Bodyx"],
            ),
            Paragraph("2. Condition and maintenance", styles["H1x"]),
        ]
    )
    for text in (
        "The landlord makes the premises available in a condition fit for ordinary residential use and maintains the premises subject to mandatory law.",
        "The tenant carries out ordinary cleaning and minor maintenance in accordance with the applicable tenancy provisions.",
        "The tenant reports defects promptly and provides reasonable access for inspection and repair. Inspections and works are announced in advance where practicable.",
    ):
        story.append(Paragraph(text, styles["Bodyx"]))

    story.extend([PageBreak(), Paragraph("3. Reporting defects", styles["H1x"])])
    for text in (
        "Defects should be reported in writing to the property management. The report should state when and where the problem was observed and whether urgent health or safety concerns exist.",
        "Photographs, correspondence and earlier repair records may be supplied with the report.",
        "The property management may arrange an inspection. The parties should retain relevant correspondence and records.",
    ):
        story.append(Paragraph(text, styles["Bodyx"]))
    story.extend(
        [
            Paragraph("4. Ventilation and heating", styles["H1x"]),
            Paragraph(
                "The tenant should heat and ventilate the apartment reasonably, taking account of season and use. Furniture should allow air to circulate near external walls and radiators.",
                styles["Bodyx"],
            ),
            Paragraph("5. Access and inspections", styles["H1x"]),
            Paragraph(
                "The tenant permits reasonable access for maintenance and investigation after suitable notice. The management records the purpose and outcome of each visit.",
                styles["Bodyx"],
            ),
            PageBreak(),
            Paragraph("6. Rent, deposit and ancillary costs", styles["H1x"]),
            Paragraph(
                "Rent is payable monthly in advance. The security deposit is held in a blocked account in the tenant's name.",
                styles["Bodyx"],
            ),
            Paragraph(
                "Ancillary costs are billed annually in accordance with the agreement and supporting account statement.",
                styles["Bodyx"],
            ),
            Paragraph("7. Communications", styles["H1x"]),
            Paragraph(
                "Notices may be sent by registered post or email where receipt can be shown. The parties should keep copies of communications and attachments.",
                styles["Bodyx"],
            ),
            Paragraph("8. Governing law", styles["H1x"]),
            Paragraph(
                "Swiss law applies. Mandatory provisions of Swiss tenancy law prevail over this agreement. Disputes may be submitted to the competent conciliation authority.",
                styles["Bodyx"],
            ),
            PageBreak(),
            Paragraph("9. Handover record - summary", styles["H1x"]),
            styled_table(
                [
                    ["Room", "Recorded condition on 30 January 2024"],
                    ["Bedroom", "Walls freshly painted; no visible moisture noted"],
                    ["Living room", "Good condition"],
                    ["Windows", "Double glazed; seals visually intact"],
                    ["Heating", "Radiators tested"],
                    ["Bathroom", "Ventilation fan operating"],
                ],
                [45 * mm, 110 * mm],
                header=True,
            ),
            Spacer(1, 16),
            Paragraph(
                "The handover record describes the visible condition recorded at the start of the tenancy.",
                styles["Smallx"],
            ),
            PageBreak(),
            Paragraph("10. House rules - relevant excerpt", styles["H1x"]),
        ]
    )
    for text in (
        "Rooms should be ventilated regularly. Furniture should not obstruct radiators or air circulation at external walls.",
        "Damage or defects should be reported without delay.",
        "Common areas and access routes should be kept clear.",
    ):
        story.append(Paragraph(text, styles["Bodyx"]))

    signature = Table(
        [
            ["Basel, 18 January 2024", "Basel, 18 January 2024"],
            ["Rheinblick Immobilien AG", "Alex Morgan"],
            ["________________________", "________________________"],
        ],
        colWidths=[77 * mm, 77 * mm],
    )
    signature.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.extend([PageBreak(), Paragraph("11. Signature fields", styles["H1x"]), signature])
    make_pdf(
        ROOT / "lease-agreement.pdf",
        title="Residential Lease Agreement",
        subtitle="Agreement dated 18 January 2024 · handover bundle completed 30 January 2024",
        story=story,
        reference="Lease reference RB-2024-0118",
        author="Rheinblick Immobilien AG",
        subject="Residential tenancy agreement",
        pdf_date="D:20240130173000+01'00'",
    )


def timeline() -> None:
    rows = [
        ["Date", "Event", "Source"],
        ["12 Mar 2026", "First small dark spots observed in bedroom corner.", "Tenant note"],
        ["20 Mar 2026", "Later message recalls the first observation as 20 March.", "Claim email"],
        ["02 Apr 2026", "Area cleaned; spots returned within approximately two weeks.", "Tenant note"],
        ["15 Jul 2026", "Written notice sent; no attachment recorded.", "Email + receipt"],
        ["18 Jul 2026", "Management replies that ventilation is the likely cause.", "Management email"],
        ["27 Jul 2026", "Mould visible again after cleaning.", "Photo"],
        ["01 Aug 2026", "Claim submitted to legal-protection insurer.", "Claim intake"],
    ]
    story: list = [
        Paragraph("Timeline supplied by the tenant", styles["H1x"]),
        styled_table(rows, [24 * mm, 93 * mm, 37 * mm], header=True),
        Spacer(1, 16),
        Paragraph("Open points", styles["H1x"]),
        Paragraph(
            "No independent inspection has been carried out. No measurements of wall temperature, humidity, air exchange or building-envelope condition are available. The tenant reports normal heating and no current health symptoms.",
            styles["Bodyx"],
        ),
        PageBreak(),
        Paragraph("Tenant observations", styles["H1x"]),
    ]
    for text in (
        "The affected area is the external corner behind, but not covered by, a wardrobe. The wardrobe stands approximately 15 cm from the wall.",
        "The bedroom radiator is used normally. The tenant reports airing the room twice daily for approximately five to ten minutes.",
        "The visible marks returned after surface cleaning. The tenant requests an inspection and repair.",
    ):
        story.append(Paragraph(text, styles["Bodyx"]))
    story.extend(
        [
            Paragraph("Date to clarify", styles["H1x"]),
            Paragraph(
                "The first-observation date is recorded as 12 March in this timeline and 20 March in the later message. The tenant should confirm which date is correct.",
                styles["Bodyx"],
            ),
        ]
    )
    make_pdf(
        ROOT / "defect-timeline.pdf",
        title="Defect Timeline",
        subtitle="Prepared 30 July 2026",
        story=story,
        reference="Tenant record AM-2026-0730",
        author="Alex Morgan",
        subject="Bedroom observations and correspondence",
        pdf_date="D:20260730194500+02'00'",
    )


def delivery_receipt() -> None:
    story: list = [
        Paragraph("Delivery record", styles["H1x"]),
        styled_table(
            [
                ["Message reference", "20260715-083200-AM"],
                ["Sent", "15 July 2026, 08:32 CEST"],
                ["Recipient", "Rheinblick Immobilien AG service desk"],
                ["Subject", "Bedroom condition - Feldbergstrasse 114"],
                ["Delivery status", "Accepted by recipient mail server"],
                ["Attachment", "None recorded"],
            ],
            [42 * mm, 112 * mm],
        ),
        Spacer(1, 14),
        Paragraph(
            "The recipient mail server accepted the message at the recorded time.",
            styles["Bodyx"],
        ),
    ]
    make_pdf(
        ROOT / "delivery-receipt.pdf",
        title="Email Delivery Receipt",
        subtitle="Delivery status recorded 15 July 2026",
        story=story,
        reference="Delivery reference 20260715-083200-AM",
        author="Mail Delivery Service",
        subject="Message delivery status",
        pdf_date="D:20260715083204+02'00'",
    )


def window_notice() -> None:
    story: list = [
        Paragraph("Window replacement completion record", styles["H1x"]),
        Paragraph(
            "The bedroom and living-room windows at Klybeckstrasse 77 were replaced between 18 and 22 May 2026. The work included insulated glazing and new perimeter seals.",
            styles["Bodyx"],
        ),
        Paragraph("Contractor record", styles["H1x"]),
        Paragraph(
            "The completion sheet records visual operation checks. It contains no indoor humidity, surface-temperature or air-exchange measurements.",
            styles["Bodyx"],
        ),
    ]
    make_pdf(
        ROOT / "window-replacement-notice.pdf",
        title="Window Replacement Completion Record",
        subtitle="Works completed 18-22 May 2026",
        story=story,
        reference="Works order RB-2026-0518",
        author="Rheinblick Immobilien AG",
        subject="Window replacement works",
        pdf_date="D:20260522170000+02'00'",
    )


def later_lease() -> None:
    story: list = [
        Paragraph("1. Parties and premises", styles["H1x"]),
        styled_table(
            [
                ["Landlord", "Rheinblick Immobilien AG, Clarastrasse 28, 4058 Basel"],
                ["Tenant", "Sam Keller, Klybeckstrasse 77, 4057 Basel"],
                ["Premises", "2-room apartment, 2nd floor, Klybeckstrasse 77, 4057 Basel"],
                ["Permitted use", "Residential use"],
                ["Start date", "1 September 2025"],
                ["Monthly net rent", "CHF 1,420"],
            ],
            [40 * mm, 115 * mm],
        ),
        Spacer(1, 12),
        Paragraph(
            "The apartment is rented to Sam Keller for residential use. The agreement "
            "covers the bedroom, living room, kitchen, bathroom and cellar compartment.",
            styles["Bodyx"],
        ),
        Paragraph("2. Defects, maintenance and access", styles["H1x"]),
        Paragraph(
            "The tenant reports defects promptly. The property management may arrange "
            "a technical inspection and gives reasonable notice before access.",
            styles["Bodyx"],
        ),
        PageBreak(),
        Paragraph("3. Communications and signature fields", styles["H1x"]),
        Paragraph(
            "Communications concerning defects may be sent to the property-management "
            "service address. The parties retain copies of relevant correspondence.",
            styles["Bodyx"],
        ),
        Spacer(1, 20),
        styled_table(
            [
                ["Agreement dated in Basel", "14 August 2025"],
                ["Landlord", "Rheinblick Immobilien AG"],
                ["Tenant", "Sam Keller"],
                ["Signature fields", "________________    ________________"],
            ],
            [40 * mm, 115 * mm],
        ),
    ]
    make_pdf(
        ROOT / "later-lease-agreement.pdf",
        title="Residential Lease Agreement",
        subtitle="Klybeckstrasse 77, Basel · agreement dated 14 August 2025",
        story=story,
        reference="Lease reference RB-2025-0814-SK",
        author="Rheinblick Immobilien AG",
        subject="Residential tenancy agreement for Sam Keller",
        pdf_date="D:20250814143000+02'00'",
    )


def write_email(path: Path, content: str) -> None:
    path.write_bytes(content.replace("\n", "\r\n").encode("utf-8"))
    set_epoch(path)


def email_files() -> None:
    notification = """From: Alex Morgan
To: Rheinblick Immobilien AG Service Team
Date: Wed, 15 Jul 2026 08:32:00 +0200
Subject: Bedroom condition - Feldbergstrasse 114
X-Archive-Reference: 20260715-083200-AM
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

Dear Service Team,

The dark mould in the external corner of the bedroom has returned after cleaning. I first noticed it in March. The radiator works and I air the room twice a day.

Please arrange an inspection and repair. I can send a current photograph and provide access on weekdays after 17:30.

Kind regards,
Alex Morgan
"""
    reply = """From: Rheinblick Immobilien AG Service Team
To: Alex Morgan
Date: Sat, 18 Jul 2026 10:14:00 +0200
Subject: Re: Bedroom condition - Feldbergstrasse 114
X-Archive-Reference: 20260718-101400-RB
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

Dear Mr Morgan,

Thank you for your message. Based on your description, the marks appear consistent with insufficient ventilation. Please air the bedroom more often and avoid placing furniture close to the external wall.

We do not currently plan a technical inspection.

Kind regards,
Rheinblick Immobilien AG
Service Team
"""
    later = """From: Sam Keller
To: Legal Protection Claims Team
Date: Mon, 10 Aug 2026 09:46:00 +0200
Subject: Recurring bedroom issue - Klybeckstrasse 77
X-Archive-Reference: 20260810-094600-SK
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

Hello,

Condensation and dark spots have appeared around the bedroom window since the windows were replaced in May. The management says I do not air enough. The problem keeps returning even though I air every morning and evening. I sent the management an email last week. No technician has inspected the window or wall.

I disagree with the management's position. I have no current health symptoms and there is no urgent deadline. I want the cause checked and the recurring condition repaired.

What should I do next?

Regards,
Sam Keller
"""
    later_notification = """From: Sam Keller
To: Rheinblick Immobilien AG Service Team
Date: Mon, 03 Aug 2026 08:17:00 +0200
Subject: Bedroom condition - Klybeckstrasse 77
X-Archive-Reference: 20260803-081700-SK
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

Dear Service Team,

Condensation and dark spots have repeatedly appeared around the bedroom window since the replacement work in May. I air the room every morning and evening.

Please arrange an inspection of the window and wall and let me know how the recurring condition will be repaired. I can provide access on weekdays after 17:00.

Kind regards,
Sam Keller
"""
    later_reply = """From: Rheinblick Immobilien AG Service Team
To: Sam Keller
Date: Wed, 05 Aug 2026 11:28:00 +0200
Subject: Re: Bedroom condition - Klybeckstrasse 77
X-Archive-Reference: 20260805-112800-RB
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

Dear Mr Keller,

We received your message of 3 August. Based on your description, we consider insufficient airing the likely cause. Please ventilate more frequently.

We do not plan a technical inspection of the window or wall at present.

Kind regards,
Rheinblick Immobilien AG
Service Team
"""
    write_email(ROOT / "notification-email.eml", notification)
    write_email(ROOT / "management-reply.eml", reply)
    write_email(ROOT / "later-claim-email.eml", later)
    write_email(ROOT / "later-notification-email.eml", later_notification)
    write_email(ROOT / "later-management-reply.eml", later_reply)


def render_pdf_pages() -> None:
    mapping = {
        "lease-agreement.pdf": "art_lease",
        "defect-timeline.pdf": "art_timeline",
        "delivery-receipt.pdf": "art_delivery",
        "window-replacement-notice.pdf": "art_window_notice",
        "later-lease-agreement.pdf": "art_later_lease",
    }
    for filename, artifact_id in mapping.items():
        pdf_path = ROOT / filename
        output = ROOT / "pages" / artifact_id
        output.mkdir(parents=True, exist_ok=True)
        document = fitz.open(pdf_path)
        for index, page in enumerate(document):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.65, 1.65), alpha=False)
            page_path = output / f"page-{index + 1}.png"
            pixmap.save(page_path)
            set_epoch(page_path)
        document.close()


def main() -> None:
    reset_output()
    lease()
    timeline()
    delivery_receipt()
    window_notice()
    later_lease()
    email_files()
    render_pdf_pages()
    for directory in sorted((path for path in ROOT.rglob("*") if path.is_dir()), reverse=True):
        set_epoch(directory)
    set_epoch(ROOT)
    print(
        "Artifact documents prepared",
        [(path.relative_to(ROOT).as_posix(), path.stat().st_size) for path in sorted(ROOT.rglob("*")) if path.is_file()],
    )


if __name__ == "__main__":
    main()
