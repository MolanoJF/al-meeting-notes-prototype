"""
Generates a branded Ackroyd Lowrie Word document from formatted meeting notes.
Client-facing meetings only.
"""

import os
import tempfile
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Inches


AL_BRAND_COLOR = RGBColor(0x1A, 0x1A, 0x2E)   # dark navy — update to AL brand hex
AL_ACCENT_COLOR = RGBColor(0x4A, 0x4A, 0x8A)


def _add_header(doc: Document, date: str, project: str):
    section = doc.sections[0]
    header = section.header
    htable = header.add_table(1, 2, width=section.page_width - section.left_margin - section.right_margin)
    htable.style = "Table Grid"
    htable.cell(0, 0).text = "Ackroyd Lowrie Architects"
    htable.cell(0, 1).text = f"{project}\n{date}"
    htable.cell(0, 1).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    for cell in htable.rows[0].cells:
        for para in cell.paragraphs:
            for run in para.runs:
                run.font.size = Pt(9)
                run.font.color.rgb = AL_BRAND_COLOR

    # Remove table borders from header
    for row in htable.rows:
        for cell in row.cells:
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            tcBorders = tcPr.get_or_add_tcBorders()
            for border in ["top", "left", "bottom", "right", "insideH", "insideV"]:
                el = tcBorders.get_or_add(qn(f"w:{border}"))
                el.set(qn("w:val"), "none")


def _add_footer(doc: Document, date: str):
    section = doc.sections[0]
    footer = section.footer
    para = footer.paragraphs[0]
    para.text = f"Confidential · Ackroyd Lowrie Architects · {date}"
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in para.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = AL_ACCENT_COLOR


def _heading(doc: Document, text: str, level: int = 1):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        run.font.color.rgb = AL_BRAND_COLOR
    return p


def generate_word_doc(formatted: dict, meeting_meta: dict) -> str:
    title = meeting_meta.get("title", "Meeting Notes")
    date = meeting_meta.get("date", datetime.today().strftime("%Y-%m-%d"))
    project = meeting_meta.get("project", "Ackroyd Lowrie")
    attendees = meeting_meta.get("attendees", [])

    doc = Document()

    _add_header(doc, date, project)
    _add_footer(doc, date)

    # Title
    title_para = doc.add_heading(title, level=0)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph(f"Date: {date}  ·  Attendees: {', '.join(attendees)}")
    doc.add_paragraph()

    # Summary
    _heading(doc, "Summary", level=1)
    doc.add_paragraph(formatted.get("summary", ""))

    # Key Decisions
    _heading(doc, "Key Decisions", level=1)
    for decision in formatted.get("key_decisions", []):
        doc.add_paragraph(decision, style="List Bullet")

    # Action Items
    _heading(doc, "Action Items", level=1)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Shading Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text = "WHO"
    hdr[1].text = "WHAT"
    hdr[2].text = "BY WHEN"
    for h in hdr:
        for run in h.paragraphs[0].runs:
            run.bold = True

    for item in formatted.get("action_items", []):
        row = table.add_row().cells
        row[0].text = item.get("who", "")
        row[1].text = item.get("what", "")
        row[2].text = item.get("by_when", "TBD")

    # Risks
    risks = formatted.get("risks_flagged", [])
    if risks:
        doc.add_paragraph()
        _heading(doc, "Open Questions / Risks", level=1)
        for risk in risks:
            doc.add_paragraph(risk, style="List Bullet")

    # Next meeting
    next_mtg = formatted.get("next_meeting")
    if next_mtg:
        doc.add_paragraph()
        doc.add_paragraph(f"Next meeting: {next_mtg}")

    # Save to temp file
    tmp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".docx",
        prefix=f"{date}-AL-",
    )
    doc.save(tmp.name)
    return tmp.name
