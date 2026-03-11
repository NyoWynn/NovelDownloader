"""
Scraper logic reused by the web backend.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,es;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
}

WAYBACK_RE = re.compile(r"https?://web\.archive\.org/web/(\d+)(?:if_)?/(https?://.*)")


def parse_wayback_url(url: str) -> tuple[str, str] | None:
    match = WAYBACK_RE.match(url)
    if match:
        return match.group(1), match.group(2)
    return None


def to_wayback_url(original_url: str, timestamp: str) -> str:
    return f"https://web.archive.org/web/{timestamp}/{original_url}"


def rewrite_link_to_wayback(href: str, base_wayback: str, timestamp: str) -> str:
    if not href or href.startswith("#"):
        return href
    if "web.archive.org" in href:
        return href
    if href.startswith("http"):
        return to_wayback_url(href, timestamp)

    wayback_info = parse_wayback_url(base_wayback)
    if wayback_info:
        _, original_base = wayback_info
        resolved = urljoin(original_base, href)
        return to_wayback_url(resolved, timestamp)

    return urljoin(base_wayback, href)


@dataclass
class ChapterInfo:
    title: str
    url: str
    number: float = 0.0


@dataclass
class NovelMetadata:
    title: str = ""
    author: str = ""
    description: str = ""
    cover_url: Optional[str] = None
    genres: list[str] = field(default_factory=list)
    chapters: list[ChapterInfo] = field(default_factory=list)
    source_url: str = ""


@dataclass
class ChapterContent:
    title: str
    paragraphs: list[str]
    number: float = 0.0


class NovelScraper:
    def __init__(
        self,
        delay: float = 1.5,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.delay = delay
        self.progress_callback = progress_callback
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _log(self, message: str):
        logger.info(message)
        if self.progress_callback:
            self.progress_callback(message)

    def _get(self, url: str, retries: int = 3) -> BeautifulSoup:
        for attempt in range(1, retries + 1):
            try:
                self._log(f"Descargando: {url[:80]}...")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                time.sleep(self.delay)
                return BeautifulSoup(response.text, "html.parser")
            except requests.RequestException as exc:
                self._log(f"Intento {attempt}/{retries} fallido: {exc}")
                if attempt < retries:
                    time.sleep(self.delay * attempt * 2)
                else:
                    raise

    def get_novel_metadata(self, url: str) -> NovelMetadata:
        wayback_info = parse_wayback_url(url)
        timestamp = wayback_info[0] if wayback_info else None
        soup = self._get(url)
        metadata = NovelMetadata(source_url=url)

        for selector in [".post-title h1", "h1.post-title", ".manga-title h1", "h1"]:
            element = soup.select_one(selector)
            if element:
                metadata.title = element.get_text(strip=True)
                break

        for selector in [
            ".author-content a",
            ".manga-authors a",
            "span.author a",
            ".post-content_item:-soup-contains('Autor') .author-content",
        ]:
            element = soup.select_one(selector)
            if element:
                metadata.author = element.get_text(strip=True)
                break

        description_element = soup.select_one(
            ".summary__content, .manga-description, .description-summary"
        )
        if description_element:
            metadata.description = "\n".join(
                paragraph.get_text(strip=True)
                for paragraph in description_element.find_all("p")
            ) or description_element.get_text(strip=True)

        for element in soup.select(".genres-content a, .manga-tags a"):
            metadata.genres.append(element.get_text(strip=True))

        cover_element = soup.select_one(
            ".summary_image img, .manga-thumbnail img, img.img-responsive"
        )
        if cover_element:
            src = cover_element.get("src") or cover_element.get("data-src") or ""
            if src and "web.archive.org" not in src and timestamp:
                src = to_wayback_url(src, timestamp)
            metadata.cover_url = src or None

        metadata.chapters = self._extract_chapter_list(soup, url, timestamp)
        return metadata

    def _extract_chapter_list(
        self, soup: BeautifulSoup, base_url: str, timestamp: Optional[str]
    ) -> list[ChapterInfo]:
        chapters: list[ChapterInfo] = []
        items = soup.select(
            ".listing-chapters_wrap li.wp-manga-chapter, .wp-manga-chapter, li.chapter"
        )
        for item in items:
            anchor = item.select_one("a")
            if not anchor:
                continue
            title = anchor.get_text(strip=True)
            href = anchor.get("href", "")
            if timestamp:
                href = rewrite_link_to_wayback(href, base_url, timestamp)
            chapters.append(ChapterInfo(title=title, url=href))

        chapters.reverse()
        for index, chapter in enumerate(chapters, start=1):
            chapter.number = _parse_chapter_number(chapter.title, index)
        return chapters

    def get_chapter_content(self, chapter: ChapterInfo) -> ChapterContent:
        soup = self._get(chapter.url)
        content_element = soup.select_one(
            ".text-left, .reading-content, .chapter-content, .entry-content, #chapter-content"
        )
        if not content_element:
            content_element = soup.select_one("article, main, .site-content")

        paragraphs: list[str] = []
        if content_element:
            for node in content_element.find_all(["p", "div"], recursive=True):
                if node.name == "div" and node.find(["p", "div", "h1", "h2", "h3"]):
                    continue
                text = node.get_text(separator=" ", strip=True)
                if text and len(text) > 5:
                    paragraphs.append(text)

        deduplicated: list[str] = []
        previous = None
        for paragraph in paragraphs:
            if paragraph != previous:
                deduplicated.append(paragraph)
            previous = paragraph

        return ChapterContent(
            title=chapter.title,
            paragraphs=deduplicated,
            number=chapter.number,
        )

    def download_chapters(
        self,
        chapters: list[ChapterInfo],
        per_chapter_callback: Optional[Callable[[int, int, str], None]] = None,
        stop_event=None,
    ) -> list[ChapterContent]:
        results: list[ChapterContent] = []
        total = len(chapters)
        for index, chapter in enumerate(chapters, start=1):
            if stop_event and stop_event.is_set():
                self._log("Descarga cancelada por el usuario.")
                break
            if per_chapter_callback:
                per_chapter_callback(index, total, chapter.title)
            try:
                results.append(self.get_chapter_content(chapter))
            except Exception as exc:
                self._log(f"Error en '{chapter.title}': {exc}")
                results.append(
                    ChapterContent(
                        title=chapter.title,
                        number=chapter.number,
                        paragraphs=[f"[Error al descargar este capitulo: {exc}]"],
                    )
                )
        return results


def _parse_chapter_number(title: str, fallback: int) -> float:
    match = re.search(r"[\d]+(?:\.\d+)?", title)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return float(fallback)
    return float(fallback)
