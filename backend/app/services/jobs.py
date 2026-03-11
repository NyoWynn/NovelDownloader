from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from ..core.pdf_generator import generate_pdf
from ..core.scraper import ChapterInfo, NovelMetadata, NovelScraper
from ..core.translator import translate_text_bundle

logger = logging.getLogger(__name__)


def safe_filename(text: str) -> str:
    import re

    safe = re.sub(r'[\\/*?:"<>|]', "", text)
    safe = safe.strip().replace(" ", "_")
    return safe[:80] or "novela"


@dataclass
class JobRecord:
    id: str
    url: str
    chapter_start: int
    chapter_end: int | None
    language: str
    status: str = "queued"
    progress: float = 0.0
    current_step: str = "Esperando..."
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    file_path: str | None = None
    file_name: str | None = None


class JobStore:
    def __init__(self):
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self._output_dir = Path(gettempdir()) / "noveldownloader-web"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def create(self, url: str, chapter_start: int, chapter_end: int | None, language: str) -> JobRecord:
        job = JobRecord(id=uuid4().hex, url=url, chapter_start=chapter_start, chapter_end=chapter_end, language=language)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **changes):
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)


job_store = JobStore()


def select_chapters(metadata: NovelMetadata, start: int, end: int | None) -> list[ChapterInfo]:
    chapters = metadata.chapters
    from_index = max(0, start - 1)
    to_index = len(chapters) if end is None else min(len(chapters), end)
    return chapters[from_index:to_index]


def run_job(job_id: str):
    job = job_store.get(job_id)
    if not job:
        return

    def update_step(message: str, progress: float | None = None):
        changes = {"current_step": message}
        if progress is not None:
            changes["progress"] = progress
        job_store.update(job_id, **changes)

    try:
        job_store.update(job_id, status="running", current_step="Leyendo metadata...", progress=0.02)
        scraper = NovelScraper(delay=1.0, progress_callback=lambda message: update_step(message))
        metadata = scraper.get_novel_metadata(job.url)
        chapters = select_chapters(metadata, job.chapter_start, job.chapter_end)
        if not chapters:
            raise ValueError("No se encontraron capitulos en el rango seleccionado.")

        def chapter_progress(current: int, total: int, title: str):
            progress = 0.1 + (current / max(total, 1)) * 0.55
            update_step(f"Descargando {current}/{total}: {title[:60]}", progress)

        contents = scraper.download_chapters(chapters, per_chapter_callback=chapter_progress)
        description = metadata.description

        if job.language == "es":
            update_step("Traduciendo contenido...", 0.72)
            description, contents = translate_text_bundle(description=description, chapters=contents, progress_callback=lambda message: update_step(message, 0.72))

        file_name = f"{safe_filename(metadata.title)}{'_es' if job.language == 'es' else ''}.pdf"
        file_path = Path(gettempdir()) / "noveldownloader-web" / f"{job.id}_{file_name}"

        update_step("Generando PDF...", 0.9)
        generate_pdf(
            output_path=str(file_path),
            novel_title=metadata.title,
            author=metadata.author,
            description=description,
            genres=metadata.genres,
            chapters=contents,
            progress_callback=lambda message: update_step(message, 0.95),
        )

        job_store.update(job_id, status="completed", progress=1.0, current_step="PDF listo para descargar.", file_path=str(file_path), file_name=file_name)
    except Exception as exc:
        logger.exception("Job failed")
        job_store.update(job_id, status="failed", error=str(exc), current_step="El trabajo fallo.")
