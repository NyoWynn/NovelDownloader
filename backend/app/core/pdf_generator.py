"""
PDF generator reused by the backend.
"""

from __future__ import annotations

import logging
from xml.sax.saxutils import escape

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
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

logger = logging.getLogger(__name__)

INK = colors.HexColor("#1A1A2E")
ACCENT = colors.HexColor("#4A3728")
TITLE_COLOR = colors.HexColor("#1A1A2E")
SUBTITLE_C = colors.HexColor("#4A3728")
RULE_COLOR = colors.HexColor("#C4A882")
META_COLOR = colors.HexColor("#6B5B4E")

PAGE_W, PAGE_H = A4
MARGIN_INNER = 3.0 * cm
MARGIN_OUTER = 2.5 * cm
MARGIN_TOP = 3.0 * cm
MARGIN_BOT = 2.8 * cm

FONTS = {
    "body": "Times-Roman",
    "body-bold": "Times-Bold",
    "body-italic": "Times-Italic",
    "heading": "Helvetica-Bold",
}


def _make_styles() -> dict[str, ParagraphStyle]:
    getSampleStyleSheet()

    def ps(name, **kwargs) -> ParagraphStyle:
        return ParagraphStyle(name, **kwargs)

    return {
        "BigTitle": ps("BigTitle", fontName=FONTS["body-bold"], fontSize=32, leading=40, textColor=TITLE_COLOR, alignment=TA_CENTER, spaceAfter=8),
        "Subtitle": ps("Subtitle", fontName=FONTS["body-italic"], fontSize=16, leading=20, textColor=SUBTITLE_C, alignment=TA_CENTER, spaceAfter=6),
        "MetaLabel": ps("MetaLabel", fontName=FONTS["body-bold"], fontSize=11, leading=14, textColor=META_COLOR, alignment=TA_CENTER),
        "MetaValue": ps("MetaValue", fontName=FONTS["body"], fontSize=11, leading=14, textColor=META_COLOR, alignment=TA_CENTER, spaceAfter=4),
        "Synopsis": ps("Synopsis", fontName=FONTS["body-italic"], fontSize=11, leading=16, textColor=INK, alignment=TA_JUSTIFY, leftIndent=1.5 * cm, rightIndent=1.5 * cm, spaceAfter=4),
        "TOCHeading": ps("TOCHeading", fontName=FONTS["heading"], fontSize=20, leading=26, textColor=ACCENT, alignment=TA_LEFT, spaceBefore=18, spaceAfter=10),
        "ChapterNumber": ps("ChapterNumber", fontName=FONTS["heading"], fontSize=11, leading=14, textColor=RULE_COLOR, alignment=TA_CENTER, spaceAfter=2),
        "ChapterTitle": ps("ChapterTitle", fontName=FONTS["body-bold"], fontSize=22, leading=28, textColor=ACCENT, alignment=TA_CENTER, spaceBefore=4, spaceAfter=16),
        "BodyText": ps("BodyText", fontName=FONTS["body"], fontSize=11, leading=18, textColor=INK, alignment=TA_JUSTIFY, firstLineIndent=1.2 * cm, spaceAfter=4),
        "BodyFirst": ps("BodyFirst", fontName=FONTS["body"], fontSize=11, leading=18, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=4),
    }


def _title_page_frame():
    return Frame(MARGIN_OUTER, MARGIN_BOT, PAGE_W - MARGIN_INNER - MARGIN_OUTER, PAGE_H - MARGIN_TOP - MARGIN_BOT, id="title_frame", showBoundary=0)


def _body_frame():
    return Frame(MARGIN_OUTER, MARGIN_BOT, PAGE_W - MARGIN_INNER - MARGIN_OUTER, PAGE_H - MARGIN_TOP - MARGIN_BOT, id="body_frame", showBoundary=0)


def _draw_header_footer(canvas, doc, novel_title: str):
    canvas.saveState()
    if doc.page > 1:
        canvas.setStrokeColor(RULE_COLOR)
        canvas.setLineWidth(0.5)
        y_line = PAGE_H - MARGIN_TOP + 4 * mm
        canvas.line(MARGIN_OUTER, y_line, PAGE_W - MARGIN_OUTER, y_line)
        canvas.setFont(FONTS["body-italic"], 8)
        canvas.setFillColor(META_COLOR)
        canvas.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN_TOP + 6 * mm, novel_title)
        y_bottom = MARGIN_BOT - 5 * mm
        canvas.line(MARGIN_OUTER, y_bottom, PAGE_W - MARGIN_OUTER, y_bottom)
        canvas.setFont(FONTS["body"], 9)
        canvas.drawCentredString(PAGE_W / 2, y_bottom - 4 * mm, str(doc.page))
    canvas.restoreState()


def _hr_table(width=None, color=RULE_COLOR, thickness=0.8):
    table = Table([[""]], colWidths=[width or (PAGE_W - MARGIN_INNER - MARGIN_OUTER)], rowHeights=[thickness])
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), thickness, color), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    return table


class _TocDocTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and getattr(flowable, "_bookmarkName", None):
            level = getattr(flowable, "_toc_level", None)
            if level is not None:
                self.notify("TOCEntry", (level, flowable.getPlainText(), self.page, flowable._bookmarkName))


def generate_pdf(output_path: str, novel_title: str, author: str, description: str, genres: list[str], chapters: list, progress_callback=None) -> str:
    styles = _make_styles()

    def log(message: str):
        logger.info(message)
        if progress_callback:
            progress_callback(message)

    doc = _TocDocTemplate(output_path, pagesize=A4, leftMargin=MARGIN_OUTER, rightMargin=MARGIN_OUTER, topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOT, title=novel_title, author=author, subject="Novela descargada por NovelDownloader Web")
    doc.addPageTemplates(
        [
            PageTemplate(id="TitlePage", frames=[_title_page_frame()], onPage=lambda canvas, doc_obj: None),
            PageTemplate(id="BodyPage", frames=[_body_frame()], onPage=lambda canvas, doc_obj: _draw_header_footer(canvas, doc_obj, novel_title)),
        ]
    )

    story = [Spacer(1, 3 * cm), _hr_table(thickness=2), Spacer(1, 0.6 * cm), Paragraph(escape(novel_title), styles["BigTitle"]), Spacer(1, 0.3 * cm), _hr_table(thickness=2), Spacer(1, 0.8 * cm)]
    if author:
        story.extend([Paragraph("Autor:", styles["MetaLabel"]), Paragraph(escape(author), styles["MetaValue"]), Spacer(1, 0.4 * cm)])
    if genres:
        story.extend([Paragraph("Generos:", styles["MetaLabel"]), Paragraph(escape(", ".join(genres)), styles["MetaValue"]), Spacer(1, 0.8 * cm)])
    if description:
        story.extend([_hr_table(thickness=0.5), Spacer(1, 0.5 * cm), Paragraph("Sinopsis", styles["Subtitle"]), Spacer(1, 0.3 * cm)])
        for line in description.split("\n"):
            if line.strip():
                story.append(Paragraph(escape(line.strip()), styles["Synopsis"]))

    story.extend([Spacer(1, 1.0 * cm), Paragraph(f"{len(chapters)} capitulos", styles["MetaValue"]), NextPageTemplate("BodyPage"), PageBreak(), Paragraph("Tabla de contenidos", styles["TOCHeading"])])
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle(name="TOCLevel1", fontName=FONTS["body"], fontSize=10, leftIndent=16, leading=14)]
    story.append(toc)
    story.append(PageBreak())

    for index, chapter in enumerate(chapters, start=1):
        log(f"Maquetando capitulo {index}/{len(chapters)}")
        bookmark = f"chapter-{index}"
        title_paragraph = Paragraph(escape(chapter.title), styles["ChapterTitle"])
        title_paragraph._bookmarkName = bookmark
        title_paragraph._toc_level = 0
        story.append(Paragraph(f"Capitulo {index}", styles["ChapterNumber"]))
        story.append(title_paragraph)
        for paragraph_index, paragraph in enumerate(chapter.paragraphs):
            story.append(Paragraph(escape(paragraph), styles["BodyFirst"] if paragraph_index == 0 else styles["BodyText"]))
        story.append(PageBreak())

    doc.build(story)
    return output_path
