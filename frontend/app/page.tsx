"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import styles from "./page.module.css";

type ChapterSummary = {
  index: number;
  title: string;
  number: number;
};

type MetadataResponse = {
  title: string;
  author: string;
  description: string;
  genres: string[];
  source_url: string;
  cover_url?: string | null;
  chapters: ChapterSummary[];
};

type JobStatus = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  current_step: string;
  error?: string | null;
  download_url?: string | null;
  file_name?: string | null;
  created_at: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  const [url, setUrl] = useState("");
  const [metadata, setMetadata] = useState<MetadataResponse | null>(null);
  const [chapterStart, setChapterStart] = useState(1);
  const [chapterEnd, setChapterEnd] = useState<number | "">("");
  const [language, setLanguage] = useState<"original" | "es">("original");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [loadingMetadata, setLoadingMetadata] = useState(false);
  const [creatingJob, setCreatingJob] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chapterCount = metadata?.chapters.length ?? 0;
  const resolvedEnd = chapterEnd === "" ? chapterCount : chapterEnd;

  useEffect(() => {
    if (!job || (job.status !== "queued" && job.status !== "running")) {
      return;
    }

    const timer = window.setInterval(async () => {
      const response = await fetch(`${API_BASE_URL}/api/jobs/${job.job_id}`);
      if (!response.ok) {
        return;
      }
      setJob(await response.json());
    }, 2500);

    return () => window.clearInterval(timer);
  }, [job]);

  const selectedRangeLabel = useMemo(() => {
    if (!metadata) {
      return "Selecciona una novela primero";
    }
    return `${chapterStart} - ${resolvedEnd || chapterCount} de ${chapterCount}`;
  }, [chapterCount, chapterStart, metadata, resolvedEnd]);

  async function handleFetchMetadata() {
    setLoadingMetadata(true);
    setError(null);
    setJob(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/metadata`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail ?? "No se pudo obtener la metadata.");
      }
      const payload: MetadataResponse = await response.json();
      setMetadata(payload);
      setChapterStart(1);
      setChapterEnd(payload.chapters.length);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Error inesperado.");
    } finally {
      setLoadingMetadata(false);
    }
  }

  async function handleCreateJob() {
    if (!metadata) {
      return;
    }

    setCreatingJob(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          chapter_start: chapterStart,
          chapter_end: resolvedEnd,
          language,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail ?? "No se pudo crear el trabajo.");
      }
      const payload = await response.json();
      setJob({
        job_id: payload.job_id,
        status: payload.status,
        progress: 0,
        current_step: "Trabajo en cola...",
        created_at: new Date().toISOString(),
      });
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : "Error inesperado.");
    } finally {
      setCreatingJob(false);
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroBadge}>Wayback to PDF</div>
        <h1>NovelDownloader Web</h1>
        <p>
          Convierte novelas archivadas en un PDF bonito, descargable y opcionalmente
          traducido al español, sin instalar una app de escritorio.
        </p>
      </section>

      <section className={styles.grid}>
        <article className={styles.card}>
          <label className={styles.label}>URL archivada de la novela</label>
          <textarea
            className={styles.urlBox}
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://web.archive.org/web/20250501021121/https://..."
          />
          <button
            className={styles.primaryButton}
            disabled={!url || loadingMetadata}
            onClick={handleFetchMetadata}
          >
            {loadingMetadata ? "Leyendo..." : "Obtener información"}
          </button>
          {error ? <p className={styles.error}>{error}</p> : null}
        </article>

        <article className={styles.card}>
          <div className={styles.sectionHeader}>
            <div>
              <span className={styles.kicker}>Salida</span>
              <h2>Configuración del PDF</h2>
            </div>
            <span className={styles.rangeChip}>{selectedRangeLabel}</span>
          </div>

          <div className={styles.controls}>
            <label>
              Desde capítulo
              <input
                type="number"
                min={1}
                max={chapterCount || 1}
                value={chapterStart}
                onChange={(event) => setChapterStart(Number(event.target.value))}
                disabled={!metadata}
              />
            </label>

            <label>
              Hasta capítulo
              <input
                type="number"
                min={1}
                max={chapterCount || 1}
                value={chapterEnd}
                onChange={(event) => setChapterEnd(Number(event.target.value))}
                disabled={!metadata}
              />
            </label>

            <label>
              Idioma
              <select
                value={language}
                onChange={(event) =>
                  setLanguage(event.target.value as "original" | "es")
                }
                disabled={!metadata}
              >
                <option value="original">Original</option>
                <option value="es">Español</option>
              </select>
            </label>
          </div>

          <button
            className={styles.secondaryButton}
            disabled={!metadata || creatingJob}
            onClick={handleCreateJob}
          >
            {creatingJob ? "Creando trabajo..." : "Generar PDF"}
          </button>
        </article>
      </section>

      {metadata ? (
        <section className={styles.preview}>
          <article className={styles.bookCard}>
            <div className={styles.coverFrame}>
              {metadata.cover_url ? (
                <Image
                  src={metadata.cover_url}
                  alt={metadata.title}
                  fill
                  className={styles.coverImage}
                  sizes="240px"
                />
              ) : (
                <div className={styles.coverFallback}>Sin portada</div>
              )}
            </div>
            <div className={styles.bookMeta}>
              <span className={styles.kicker}>Novela detectada</span>
              <h2>{metadata.title}</h2>
              <p>{metadata.author || "Autor desconocido"}</p>
              <div className={styles.genreRow}>
                {metadata.genres.map((genre) => (
                  <span key={genre} className={styles.genre}>
                    {genre}
                  </span>
                ))}
              </div>
            </div>
          </article>

          <article className={styles.listCard}>
            <div className={styles.sectionHeader}>
              <div>
                <span className={styles.kicker}>Capítulos</span>
                <h2>{metadata.chapters.length} encontrados</h2>
              </div>
            </div>

            <div className={styles.chapterList}>
              {metadata.chapters.slice(0, 18).map((chapter) => (
                <div key={`${chapter.index}-${chapter.title}`} className={styles.chapterItem}>
                  <span>#{chapter.index}</span>
                  <p>{chapter.title}</p>
                </div>
              ))}
            </div>

            {metadata.chapters.length > 18 ? (
              <p className={styles.muted}>
                Mostrando los primeros 18 capítulos. El backend usará el rango real que
                selecciones.
              </p>
            ) : null}
          </article>
        </section>
      ) : null}

      {job ? (
        <section className={styles.jobCard}>
          <div className={styles.sectionHeader}>
            <div>
              <span className={styles.kicker}>Trabajo</span>
              <h2>
                {job.status === "completed"
                  ? "PDF listo"
                  : job.status === "failed"
                    ? "Algo falló"
                    : "Procesando"}
              </h2>
            </div>
            <span className={styles.statusPill}>{job.status}</span>
          </div>

          <div className={styles.progressBar}>
            <div style={{ width: `${Math.round(job.progress * 100)}%` }} />
          </div>
          <p className={styles.muted}>{job.current_step}</p>
          {job.error ? <p className={styles.error}>{job.error}</p> : null}
          {job.download_url ? (
            <a
              className={styles.primaryButton}
              href={`${API_BASE_URL}${job.download_url}`}
              target="_blank"
              rel="noreferrer"
            >
              Descargar {job.file_name ?? "PDF"}
            </a>
          ) : null}
        </section>
      ) : null}

      <footer className={styles.footer}>
        <span>Marca de agua por WynnDev</span>
        <a href="https://github.com/NyoWynn" target="_blank" rel="noreferrer">
          github.com/NyoWynn
        </a>
      </footer>
    </main>
  );
}
