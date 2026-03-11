"""
translator.py
Helpers for optional translation of the extracted novel content.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from deep_translator import GoogleTranslator

from scraper import ChapterContent

logger = logging.getLogger(__name__)

CHUNK_SIZE = 4500


def _translate_text(text: str, translator: GoogleTranslator) -> str:
    if not text.strip():
        return text

    try:
        parts = []
        for idx in range(0, len(text), CHUNK_SIZE):
            chunk = text[idx : idx + CHUNK_SIZE]
            parts.append(translator.translate(chunk))
        return "".join(parts)
    except Exception:
        logger.exception("Translation failed, keeping original text.")
        return text


def translate_text_bundle(
    description: str,
    chapters: list[ChapterContent],
    progress_callback=None,
) -> tuple[str, list[ChapterContent]]:
    translator = GoogleTranslator(source="auto", target="es")

    def log(message: str):
        logger.info(message)
        if progress_callback:
            progress_callback(message)

    translated_description = description
    if description.strip():
        log("Traduciendo sinopsis...")
        translated_description = _translate_text(description, translator)

    translated_chapters: list[ChapterContent] = []
    total = len(chapters)
    for index, chapter in enumerate(chapters, start=1):
        log(f"Traduciendo capitulo {index}/{total}: {chapter.title[:50]}")
        translated_title = _translate_text(chapter.title, translator)
        translated_paragraphs = [
            _translate_text(paragraph, translator)
            for paragraph in chapter.paragraphs
        ]
        translated_chapters.append(
            replace(
                chapter,
                title=translated_title,
                paragraphs=translated_paragraphs,
            )
        )

    return translated_description, translated_chapters
