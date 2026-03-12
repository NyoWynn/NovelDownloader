from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class MetadataRequest(BaseModel):
    url: str = Field(..., min_length=10)


class ChapterSummary(BaseModel):
    index: int
    title: str
    number: float


class MetadataResponse(BaseModel):
    title: str
    author: str
    description: str
    genres: list[str]
    source_url: str
    cover_url: Optional[str] = None
    chapters: list[ChapterSummary]


class JobCreateRequest(BaseModel):
    url: str = Field(..., min_length=10)
    chapter_start: int = Field(1, ge=1)
    chapter_end: Optional[int] = Field(None, ge=1)
    language: Literal["original", "es"] = "original"


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: float = Field(0, ge=0, le=1)
    current_step: str = ""
    error: Optional[str] = None
    download_url: Optional[str] = None
    file_name: Optional[str] = None
    created_at: datetime
