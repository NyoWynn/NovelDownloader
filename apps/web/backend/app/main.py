from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .core.scraper import NovelScraper
from .schemas import ChapterSummary, JobCreateRequest, JobCreateResponse, JobStatusResponse, MetadataRequest, MetadataResponse
from .services.jobs import job_store, run_job

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

app = FastAPI(title="NovelDownloader API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:3000",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/metadata", response_model=MetadataResponse)
def fetch_metadata(payload: MetadataRequest):
    scraper = NovelScraper(delay=1.0)
    metadata = scraper.get_novel_metadata(payload.url)
    return MetadataResponse(
        title=metadata.title,
        author=metadata.author,
        description=metadata.description,
        genres=metadata.genres,
        source_url=metadata.source_url,
        cover_url=metadata.cover_url,
        chapters=[ChapterSummary(index=index, title=chapter.title, number=chapter.number) for index, chapter in enumerate(metadata.chapters, start=1)],
    )


@app.post("/api/jobs", response_model=JobCreateResponse)
def create_job(payload: JobCreateRequest):
    job = job_store.create(url=payload.url, chapter_start=payload.chapter_start, chapter_end=payload.chapter_end, language=payload.language)
    threading.Thread(target=run_job, args=(job.id,), daemon=True).start()
    return JobCreateResponse(job_id=job.id, status=job.status)


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado.")

    download_url = f"/api/jobs/{job_id}/download" if job.status == "completed" and job.file_path else None
    return JobStatusResponse(job_id=job.id, status=job.status, progress=job.progress, current_step=job.current_step, error=job.error, download_url=download_url, file_name=job.file_name, created_at=job.created_at)


@app.get("/api/jobs/{job_id}/download")
def download_job_file(job_id: str):
    job = job_store.get(job_id)
    if not job or not job.file_path or job.status != "completed":
        raise HTTPException(status_code=404, detail="Archivo no disponible.")
    path = Path(job.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco.")
    return FileResponse(path=path, filename=job.file_name, media_type="application/pdf")
