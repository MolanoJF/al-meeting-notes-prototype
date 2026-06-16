"""
Generates a branded Ackroyd Lowrie Word document from formatted meeting notes.
Client-facing meetings only.

Styling matches the firm's reference template exactly (extracted from
AL_meeting_automation_summary.docx): Arial throughout, logo-only header
(no footer/page numbers — the reference doc doesn't have them either),
A4 page, specific heading/title colors and sizes.
"""

import os
import tempfile
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Mm, Emu

HEADING_COLOR = RGBColor(0x1F, 0x29, 0x37)   # dark gray-black, matches reference Heading 1
SUBTITLE_COLOR = RGBColor(0x6B, 0x72, 0x80)  # slate gray, matches reference intro paragraph

LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "al_logo.jpg")
LOGO_WIDTH_EMU = 1238250   # exact width from the reference header image
LOGO_HEIGHT_EMU = 314325

A4_WIDTH = Mm(210)
A4_HEIGHT = Mm(297)


def _set_base_font(doc: Document):
    """Arial everywhere, 10pt body — matches reference docDefaults."""
    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(10)
    rpr = normal.element.get_or_add_rPr()
    rFonts = rpr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rFonts.set(qn(attr), "Arial")


def _style_title(doc: Document):
    title = doc.styles["Title"]
    title.font.name = "Arial"
    title.font.size = Pt(28)
    title.font.bold = False


def _style_heading1(doc: Document):
    h1 = doc.styles["Heading 1"]
    h1.font.name = "Arial"
    h1.font.size = Pt(11)
    h1.font.bold = True
    h1.font.color.rgb = HEADING_COLOR


def _style_list_bullet(doc: Document):
    # "List Bullet" defaults to Calibri regardless of Normal's font — force Arial.
    lb = doc.styles["List Bullet"]
    lb.font.name = "Arial"
    lb.font.size = Pt(10)


def _set_page_geometry(doc: Document):
    section = doc.sections[0]
    section.page_width = A4_WIDTH
    section.page_height = A4_HEIGHT
    section.top_margin = Pt(54)
    section.left_margin = Pt(54)
    section.right_margin = Pt(54)
    section.bottom_margin = Pt(45)


def _add_header_logo(doc: Document):
    """Logo only, right-aligned — matches the reference header exactly (no text)."""
    section = doc.sections[0]
    header = section.header
    para = header.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if os.path.exists(LOGO_PATH):
        run = para.add_run()
        run.add_picture(LOGO_PATH, width=Emu(LOGO_WIDTH_EMU), height=Emu(LOGO_HEIGHT_EMU))


def generate_word_doc(formatted: dict, meeting_meta: dict) -> str:
    title = meeting_meta.get("title", "Meeting Notes")
    date = meeting_meta.get("date", datetime.today().strftime("%Y-%m-%d"))
    attendees = meeting_meta.get("attendees", [])

    doc = Document()

    _set_base_font(doc)
    _style_title(doc)
    _style_heading1(doc)
    _style_list_bullet(doc)
    _set_page_geometry(doc)
    _add_header_logo(doc)

    # Title
    doc.add_heading(title, level=0)

    # Subtitle line — gray, matches reference intro paragraph style
    subtitle = doc.add_paragraph(f"{date}  ·  {', '.join(attendees)}")
    for run in subtitle.runs:
        run.font.color.rgb = SUBTITLE_COLOR

    # Summary
    doc.add_heading("Summary", level=1)
    doc.add_paragraph(formatted.get("summary", ""))

    # Key Decisions
    doc.add_heading("Key Decisions", level=1)
    for decision in formatted.get("key_decisions", []):
        doc.add_paragraph(decision, style="List Bullet")

    # Action Items
    doc.add_heading("Action Items", level=1)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Shading Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text = "WHO"
    hdr[1].text = "WHAT"
    hdr[2].text = "BY WHEN"
    for h in hdr:
        for run in h.paragraphs[0].runs:
            run.font.name = "Arial"
            run.bold = True

    for item in formatted.get("action_items", []):
        row = table.add_row().cells
        row[0].text = item.get("who", "")
        row[1].text = item.get("what", "")
        row[2].text = item.get("by_when", "TBD")

    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.name = "Arial"
                    run.font.size = Pt(10)

    # Risks
    risks = formatted.get("risks_flagged", [])
    if risks:
        doc.add_heading("Open Questions / Risks", level=1)
        for risk in risks:
            doc.add_paragraph(risk, style="List Bullet")

    # Next meeting
    next_mtg = formatted.get("next_meeting")
    if next_mtg:
        doc.add_heading("Next Meeting", level=1)
        doc.add_paragraph(next_mtg)

    tmp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".docx",
        prefix=f"{date}-AL-",
    )
    doc.save(tmp.name)
    return tmp.name
