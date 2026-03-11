"""
scraper.py
Core scraping logic for the Novel Downloader.
Handles Wayback Machine (web.archive.org) URLs and standard novel sites
using the WordPress Madara theme structure.
"""

import re
import time
import logging
from urllib.parse import urlparse, urljoin, quote
from dataclasses import dataclass, field
from typing import Optional, Callable

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

# ─── Wayback Machine helpers ─────────────────────────────────────────────────

WAYBACK_RE = re.compile(
    r"https?://web\.archive\.org/web/(\d+)(?:if_)?/(https?://.*)"
)


def parse_wayback_url(url: str) -> tuple[str, str] | None:
    """
    If *url* is a Wayback Machine URL, return (timestamp, original_url).
    Otherwise return None.
    """
    m = WAYBACK_RE.match(url)
    if m:
        return m.group(1), m.group(2)
    return None


def to_wayback_url(original_url: str, timestamp: str) -> str:
    """Wrap an original URL in a Wayback Machine URL using a given timestamp."""
    return f"https://web.archive.org/web/{timestamp}/{original_url}"


def rewrite_link_to_wayback(href: str, base_wayback: str, timestamp: str) -> str:
    """
    Given an <a href> from inside a Wayback Machine page, return the correct
    Wayback Machine URL to that link.

    Handles:
    - Absolute URLs already pointing to web.archive.org
    - Absolute original URLs (https://lunarletters.com/...)
    - Relative URLs
    """
    if not href or href.startswith("#"):
        return href

    # Already a Wayback URL
    if "web.archive.org" in href:
        return href

    # Absolute original URL
    if href.startswith("http"):
        return to_wayback_url(href, timestamp)

    # Relative URL — we need to resolve against the *original* URL
    wb = parse_wayback_url(base_wayback)
    if wb:
        _, original_base = wb
        resolved = urljoin(original_base, href)
        return to_wayback_url(resolved, timestamp)

    return urljoin(base_wayback, href)


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ChapterInfo:
    title: str
    url: str          # Full Wayback Machine URL (or original URL)
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


# ─── Main scraper class ───────────────────────────────────────────────────────

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

    def _log(self, msg: str):
        logger.info(msg)
        if self.progress_callback:
            self.progress_callback(msg)

    def _get(self, url: str, retries: int = 3) -> BeautifulSoup:
        """Fetch URL and return a BeautifulSoup object.  Retries on failure."""
        for attempt in range(1, retries + 1):
            try:
                self._log(f"Descargando: {url[:80]}…")
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                time.sleep(self.delay)
                return BeautifulSoup(resp.text, "lxml")
            except requests.RequestException as exc:
                self._log(f"  ⚠ Intento {attempt}/{retries} fallido: {exc}")
                if attempt < retries:
                    time.sleep(self.delay * attempt * 2)
                else:
                    raise

    # ── Metadata ──────────────────────────────────────────────────────────────

    def get_novel_metadata(self, url: str) -> NovelMetadata:
        """
        Fetch the main novel/manga index page and return NovelMetadata
        including the full ordered chapter list.
        """
        wb_info = parse_wayback_url(url)
        timestamp = wb_info[0] if wb_info else None

        soup = self._get(url)
        meta = NovelMetadata(source_url=url)

        # Title
        for sel in [".post-title h1", "h1.post-title", ".manga-title h1", "h1"]:
            el = soup.select_one(sel)
            if el:
                meta.title = el.get_text(strip=True)
                break

        # Author
        for sel in [
            ".author-content a",
            ".manga-authors a",
            "span.author a",
            ".post-content_item:-soup-contains('Autor') .author-content",
        ]:
            el = soup.select_one(sel)
            if el:
                meta.author = el.get_text(strip=True)
                break

        # Description
        desc_el = soup.select_one(
            ".summary__content, .manga-description, .description-summary"
        )
        if desc_el:
            meta.description = "\n".join(
                p.get_text(strip=True) for p in desc_el.find_all("p")
            ) or desc_el.get_text(strip=True)

        # Genres
        for el in soup.select(".genres-content a, .manga-tags a"):
            meta.genres.append(el.get_text(strip=True))

        # Cover image
        cover_el = soup.select_one(
            ".summary_image img, .manga-thumbnail img, img.img-responsive"
        )
        if cover_el:
            src = cover_el.get("src") or cover_el.get("data-src") or ""
            if src and "web.archive.org" not in src and timestamp:
                src = to_wayback_url(src, timestamp)
            meta.cover_url = src or None

        # Chapter list
        meta.chapters = self._extract_chapter_list(soup, url, timestamp)
        return meta

    def _extract_chapter_list(
        self, soup: BeautifulSoup, base_url: str, timestamp: Optional[str]
    ) -> list[ChapterInfo]:
        chapters: list[ChapterInfo] = []

        # Madara theme: li.wp-manga-chapter inside .listing-chapters_wrap
        items = soup.select(
            ".listing-chapters_wrap li.wp-manga-chapter, "
            ".wp-manga-chapter, "
            "li.chapter"
        )

        for item in items:
            a = item.select_one("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if timestamp:
                href = rewrite_link_to_wayback(href, base_url, timestamp)
            chapters.append(ChapterInfo(title=title, url=href))

        # The Madara theme lists chapters in descending order → reverse
        chapters.reverse()

        # Assign sequential chapter numbers
        for i, ch in enumerate(chapters, start=1):
            ch.number = _parse_chapter_number(ch.title, i)

        return chapters

    # ── Chapter content ────────────────────────────────────────────────────────

    def get_chapter_content(self, chapter: ChapterInfo) -> ChapterContent:
        """Download a single chapter and return its text paragraphs."""
        soup = self._get(chapter.url)

        # Try multiple selectors for the reading content area
        content_el = soup.select_one(
            ".text-left, "
            ".reading-content, "
            ".chapter-content, "
            ".entry-content, "
            "#chapter-content"
        )

        if not content_el:
            # Fallback: grab the <article> or <main> tag
            content_el = soup.select_one("article, main, .site-content")

        paragraphs = []
        if content_el:
            for p in content_el.find_all(["p", "div"], recursive=True):
                # Skip divs that are containers (have block children)
                if p.name == "div" and p.find(["p", "div", "h1", "h2", "h3"]):
                    continue
                text = p.get_text(separator=" ", strip=True)
                if text and len(text) > 5:
                    paragraphs.append(text)

        # Deduplicate consecutive identical paragraphs (Wayback duplications)
        seen = []
        prev = None
        for para in paragraphs:
            if para != prev:
                seen.append(para)
            prev = para

        return ChapterContent(
            title=chapter.title,
            number=chapter.number,
            paragraphs=seen,
        )

    def download_chapters(
        self,
        chapters: list[ChapterInfo],
        per_chapter_callback: Optional[Callable[[int, int, str], None]] = None,
        stop_event=None,
    ) -> list[ChapterContent]:
        """
        Download all given chapters in order.

        per_chapter_callback(current_index, total, chapter_title) is called
        before each chapter download.
        stop_event: a threading.Event — if set, stops the download loop.
        """
        results = []
        total = len(chapters)
        for i, ch in enumerate(chapters, start=1):
            if stop_event and stop_event.is_set():
                self._log("Descarga cancelada por el usuario.")
                break
            if per_chapter_callback:
                per_chapter_callback(i, total, ch.title)
            try:
                content = self.get_chapter_content(ch)
                results.append(content)
            except Exception as exc:
                self._log(f"  ✗ Error en «{ch.title}»: {exc}")
                # Add a placeholder so we don't silently skip chapters
                results.append(
                    ChapterContent(
                        title=ch.title,
                        number=ch.number,
                        paragraphs=[f"[Error al descargar este capítulo: {exc}]"],
                    )
                )
        return results


# ─── Utilities ────────────────────────────────────────────────────────────────

def _parse_chapter_number(title: str, fallback: int) -> float:
    """Try to extract a chapter number from the title string."""
    m = re.search(r"[\d]+(?:\.\d+)?", title)
    if m:
        try:
            return float(m.group())
        except ValueError:
            pass
    return float(fallback)
