"""
pdf_generator.py
Generates a beautifully formatted PDF from scraped novel content.
Uses ReportLab for full typographic control.
"""

import io
import logging
import os
import textwrap
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

# ─── Color palette (Book-like warm tones) ─────────────────────────────────────
INK         = colors.HexColor("#1A1A2E")       # Near-black for body text
ACCENT      = colors.HexColor("#4A3728")       # Dark brown for chapter headings
TITLE_COLOR = colors.HexColor("#1A1A2E")
SUBTITLE_C  = colors.HexColor("#4A3728")
RULE_COLOR  = colors.HexColor("#C4A882")       # Warm gold rule lines
PAGE_BG     = colors.white
LIGHT_GREY  = colors.HexColor("#F5F0E8")       # Cream for decorative boxes
META_COLOR  = colors.HexColor("#6B5B4E")       # Muted for metadata text

PAGE_W, PAGE_H = A4
MARGIN_INNER = 3.0 * cm
MARGIN_OUTER = 2.5 * cm
MARGIN_TOP   = 3.0 * cm
MARGIN_BOT   = 2.8 * cm


# ─── Font registration ─────────────────────────────────────────────────────────

def _register_fonts():
    """Register built-in Type1 fonts we'll use. Returns dict of font names."""
    # ReportLab ships with standard PDF Type1 fonts — no TTF file needed.
    # We map logical names to real PDF font names.
    return {
        "body":       "Times-Roman",
        "body-bold":  "Times-Bold",
        "body-italic":"Times-Italic",
        "heading":    "Helvetica-Bold",
        "heading-reg":"Helvetica",
        "mono":       "Courier",
    }


FONTS = _register_fonts()


# ─── Stylesheet ────────────────────────────────────────────────────────────────

def _make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()

    def ps(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, **kw)

    styles = {
        # ── Title page ──────────────────────────────────────
        "BigTitle": ps(
            "BigTitle",
            fontName=FONTS["body-bold"],
            fontSize=32,
            leading=40,
            textColor=TITLE_COLOR,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "Subtitle": ps(
            "Subtitle",
            fontName=FONTS["body-italic"],
            fontSize=16,
            leading=20,
            textColor=SUBTITLE_C,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "MetaLabel": ps(
            "MetaLabel",
            fontName=FONTS["body-bold"],
            fontSize=11,
            leading=14,
            textColor=META_COLOR,
            alignment=TA_CENTER,
        ),
        "MetaValue": ps(
            "MetaValue",
            fontName=FONTS["body"],
            fontSize=11,
            leading=14,
            textColor=META_COLOR,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "Synopsis": ps(
            "Synopsis",
            fontName=FONTS["body-italic"],
            fontSize=11,
            leading=16,
            textColor=INK,
            alignment=TA_JUSTIFY,
            leftIndent=1.5 * cm,
            rightIndent=1.5 * cm,
            spaceAfter=4,
        ),
        # ── TOC ─────────────────────────────────────────────
        "TOCHeading": ps(
            "TOCHeading",
            fontName=FONTS["heading"],
            fontSize=20,
            leading=26,
            textColor=ACCENT,
            alignment=TA_LEFT,
            spaceBefore=18,
            spaceAfter=10,
        ),
        "TOCEntry": ps(
            "TOCEntry",
            fontName=FONTS["body"],
            fontSize=10,
            leading=14,
            textColor=INK,
            alignment=TA_LEFT,
        ),
        # ── Chapter headings ─────────────────────────────────
        "ChapterNumber": ps(
            "ChapterNumber",
            fontName=FONTS["heading"],
            fontSize=11,
            leading=14,
            textColor=RULE_COLOR,
            alignment=TA_CENTER,
            spaceBefore=0,
            spaceAfter=2,
        ),
        "ChapterTitle": ps(
            "ChapterTitle",
            fontName=FONTS["body-bold"],
            fontSize=22,
            leading=28,
            textColor=ACCENT,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=16,
        ),
        # ── Body text ─────────────────────────────────────────
        "BodyText": ps(
            "BodyText",
            fontName=FONTS["body"],
            fontSize=11,
            leading=18,
            textColor=INK,
            alignment=TA_JUSTIFY,
            firstLineIndent=1.2 * cm,
            spaceAfter=4,
        ),
        "BodyFirst": ps(
            "BodyFirst",
            fontName=FONTS["body"],
            fontSize=11,
            leading=18,
            textColor=INK,
            alignment=TA_JUSTIFY,
            firstLineIndent=0,
            spaceAfter=4,
        ),
        # ── Footer ───────────────────────────────────────────
        "Footer": ps(
            "Footer",
            fontName=FONTS["body-italic"],
            fontSize=8,
            leading=10,
            textColor=META_COLOR,
            alignment=TA_CENTER,
        ),
    }
    return styles


# ─── Page template callbacks ───────────────────────────────────────────────────

def _title_page_frame():
    return Frame(
        MARGIN_OUTER,
        MARGIN_BOT,
        PAGE_W - MARGIN_INNER - MARGIN_OUTER,
        PAGE_H - MARGIN_TOP - MARGIN_BOT,
        id="title_frame",
        showBoundary=0,
    )


def _body_frame():
    return Frame(
        MARGIN_OUTER,
        MARGIN_BOT,
        PAGE_W - MARGIN_INNER - MARGIN_OUTER,
        PAGE_H - MARGIN_TOP - MARGIN_BOT,
        id="body_frame",
        showBoundary=0,
    )


def _draw_header_footer(canvas, doc, novel_title: str):
    canvas.saveState()
    page_num = doc.page

    if page_num > 1:
        # Decorative top rule (skip on cover)
        canvas.setStrokeColor(RULE_COLOR)
        canvas.setLineWidth(0.5)
        y_line = PAGE_H - MARGIN_TOP + 4 * mm
        canvas.line(MARGIN_OUTER, y_line, PAGE_W - MARGIN_OUTER, y_line)

        # Novel title in header
        canvas.setFont(FONTS["body-italic"], 8)
        canvas.setFillColor(META_COLOR)
        canvas.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN_TOP + 6 * mm, novel_title)

        # Bottom rule
        y_bot = MARGIN_BOT - 5 * mm
        canvas.setStrokeColor(RULE_COLOR)
        canvas.line(MARGIN_OUTER, y_bot, PAGE_W - MARGIN_OUTER, y_bot)

        # Page number
        canvas.setFont(FONTS["body"], 9)
        canvas.setFillColor(META_COLOR)
        canvas.drawCentredString(PAGE_W / 2, y_bot - 4 * mm, str(page_num))

    canvas.restoreState()


# ─── Horizontal rule helper ────────────────────────────────────────────────────

def _hr_table(width=None, color=RULE_COLOR, thickness=0.8):
    """Return a Table that renders as a horizontal rule."""
    w = width or (PAGE_W - MARGIN_INNER - MARGIN_OUTER)
    t = Table([[""] ], colWidths=[w], rowHeights=[thickness])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), thickness, color),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


# ─── Main PDF generator function ──────────────────────────────────────────────

def generate_pdf(
    output_path: str,
    novel_title: str,
    author: str,
    description: str,
    genres: list[str],
    chapters: list,          # list[ChapterContent]
    progress_callback=None,
) -> str:
    """
    Build and save the PDF.
    Returns the output path on success.
    chapters: list of ChapterContent dataclass instances.
    """

    styles = _make_styles()

    def log(msg):
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    log("Iniciando generación de PDF…")

    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN_OUTER,
        rightMargin=MARGIN_OUTER,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOT,
        title=novel_title,
        author=author,
        subject="Novela descargada por Novel Downloader",
    )

    # ── Page templates ────────────────────────────────────────────────────────
    def on_page(canvas, doc_):
        _draw_header_footer(canvas, doc_, novel_title)

    title_template = PageTemplate(
        id="TitlePage",
        frames=[_title_page_frame()],
        onPage=lambda c, d: None,   # No header/footer on cover
    )
    body_template = PageTemplate(
        id="BodyPage",
        frames=[_body_frame()],
        onPage=on_page,
    )
    doc.addPageTemplates([title_template, body_template])

    # ── Build story ───────────────────────────────────────────────────────────
    story = []

    # ╔═══════════════════════════════╗
    # ║       COVER / TITLE PAGE      ║
    # ╚═══════════════════════════════╝
    story.append(Spacer(1, 3 * cm))
    story.append(_hr_table(color=RULE_COLOR, thickness=2))
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(_escape(novel_title), styles["BigTitle"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(_hr_table(color=RULE_COLOR, thickness=2))
    story.append(Spacer(1, 0.8 * cm))

    if author:
        story.append(Paragraph("Autor:", styles["MetaLabel"]))
        story.append(Paragraph(_escape(author), styles["MetaValue"]))
        story.append(Spacer(1, 0.4 * cm))

    if genres:
        story.append(Paragraph("Géneros:", styles["MetaLabel"]))
        story.append(Paragraph(_escape(", ".join(genres)), styles["MetaValue"]))
        story.append(Spacer(1, 0.8 * cm))

    if description:
        story.append(_hr_table(color=RULE_COLOR, thickness=0.5))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("Sinopsis", styles["Subtitle"]))
        story.append(Spacer(1, 0.3 * cm))
        for line in description.split("\n"):
            line = line.strip()
            if line:
                story.append(Paragraph(_escape(line), styles["Synopsis"]))
        story.append(Spacer(1, 0.5 * cm))
        story.append(_hr_table(color=RULE_COLOR, thickness=0.5))

    # Chapters count badge
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(f"{len(chapters)} Capítulos", styles["Subtitle"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Novel Downloader", styles["MetaValue"]))

    # ── Switch to body template ────────────────────────────────────────────
    story.append(NextPageTemplate("BodyPage"))
    story.append(PageBreak())

    # ╔═══════════════════════════════╗
    # ║         CHAPTER PAGES         ║
    # ╚═══════════════════════════════╝
    total_chapters = len(chapters)
    for idx, chapter in enumerate(chapters, start=1):
        log(f"  PDF: escribiendo capítulo {idx}/{total_chapters} — {chapter.title}")

        # Chapter header
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(f"— Capítulo {idx} —", styles["ChapterNumber"]))
        story.append(Paragraph(_escape(chapter.title), styles["ChapterTitle"]))
        story.append(_hr_table(color=RULE_COLOR, thickness=0.5))
        story.append(Spacer(1, 0.4 * cm))

        # Paragraphs
        for i, para in enumerate(chapter.paragraphs):
            if not para.strip():
                continue
            style = styles["BodyFirst"] if i == 0 else styles["BodyText"]
            story.append(Paragraph(_escape(para), style))

        if not chapter.paragraphs:
            story.append(Paragraph("[Capítulo sin contenido]", styles["BodyText"]))

        # Page break between chapters (except after the last one)
        if idx < total_chapters:
            story.append(PageBreak())

    log("Compilando PDF…")
    doc.build(story)
    log(f"✓ PDF guardado en: {output_path}")
    return output_path


def _escape(text: str) -> str:
    """Escape special XML/HTML characters for ReportLab Paragraph."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
    )
