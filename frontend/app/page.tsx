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

const STATUS_LABELS: Record<JobStatus["status"], string> = {
  queued: "EN COLA",
  running: "RUNNING",
  completed: "LISTO",
  failed: "ERROR",
};

const LANGUAGE_LABELS = {
  original: "Original",
  es: "Español",
};

export default function HomePage() {
  const [url, setUrl] = useState("");
  const [metadata, setMetadata] = useState<MetadataResponse | null>(null);
  const [chapterStart, setChapterStart] = useState(1);
  const [chapterEnd, setChapterEnd] = useState<number | "">("");
  const [language, setLanguage] = useState<"original" | "es">("es");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [loadingMetadata, setLoadingMetadata] = useState(false);
  const [creatingJob, setCreatingJob] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chapterCount = metadata?.chapters.length ?? 0;
  const resolvedEnd = chapterEnd === "" ? chapterCount : chapterEnd;
  const visibleChapters = metadata?.chapters.slice(0, 8) ?? [];

  useEffect(() => {
    if (!job || (job.status !== "queued" && job.status !== "running")) {
      return;
    }

    const timer = window.setInterval(async () => {
      const response = await fetch(`${API_BASE_URL}/api/jobs/${job.job_id}`);
      if (!response.ok) {
        return;
      }
      const nextJob: JobStatus = await response.json();
      setJob(nextJob);
    }, 2200);

    return () => window.clearInterval(timer);
  }, [job]);

  const chapterPill = useMemo(() => {
    if (!metadata) {
      return "0 encontrados";
    }
    return `${metadata.chapters.length} encontrados`;
  }, [metadata]);

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
        current_step: "Preparando trabajo...",
        created_at: new Date().toISOString(),
      });
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : "Error inesperado.");
    } finally {
      setCreatingJob(false);
    }
  }

  return (
    <main className={styles.pageShell}>
      <div className={styles.topBand} />

      <section className={styles.heroCard}>
        <div className={styles.heroArt}>
          <div className={styles.heroArtGlow} />
          <Image
            src="/logo.png"
            alt="NovelDownloader"
            width={124}
            height={124}
            className={styles.heroLogo}
            priority
          />
        </div>

        <div className={styles.heroCopy}>
          <h1>NovelDownloader Web</h1>
          <p>
            Convierte novelas archivadas en un PDF bonito, descargable y
            opcionalmente traducido al español, sin instalar una app de escritorio.
          </p>
        </div>
      </section>

      <section className={styles.mainGrid}>
        <div className={styles.leftColumn}>
          <article className={`${styles.panel} ${styles.inputPanel}`}>
            <div className={styles.panelTitleRow}>
              <span className={styles.panelIcon}>▣</span>
              <h2>URL archivada de la novela</h2>
            </div>

            <div className={styles.urlCard}>
              <textarea
                className={styles.urlInput}
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://web.archive.org/web/20231211101815/https://lunarletters.com/manga/climax/"
              />

              <button
                className={styles.ctaButton}
                disabled={!url || loadingMetadata}
                onClick={handleFetchMetadata}
              >
                {loadingMetadata ? "Obteniendo..." : "Obtener información"}
                <span className={styles.ctaIcon}>⌕</span>
              </button>
            </div>

            {error ? <p className={styles.errorText}>{error}</p> : null}
          </article>

          <article className={`${styles.panel} ${styles.jobPanel}`}>
            <div className={styles.jobHeader}>
              <div>
                <h3>Trabajo</h3>
                <div className={styles.jobHeadline}>
                  {job
                    ? job.status === "completed"
                      ? "Completado"
                      : job.status === "failed"
                        ? "Falló"
                        : "Procesando"
                    : "Esperando"}
                </div>
              </div>

              <div
                className={`${styles.statusBadge} ${
                  job?.status === "failed"
                    ? styles.statusFailed
                    : job?.status === "completed"
                      ? styles.statusDone
                      : styles.statusRunning
                }`}
              >
                <span className={styles.statusSpinner} />
                {STATUS_LABELS[job?.status ?? "queued"]}
              </div>
            </div>

            <div className={styles.progressTrack}>
              <div
                className={styles.progressValue}
                style={{ width: `${Math.max(0.06, job?.progress ?? 0) * 100}%` }}
              />
            </div>

            <p className={styles.jobText}>
              {job?.current_step ?? "Todavía no hay un trabajo corriendo."}
            </p>

            {job?.download_url ? (
              <a
                className={styles.downloadButton}
                href={`${API_BASE_URL}${job.download_url}`}
                target="_blank"
                rel="noreferrer"
              >
                Descargar {job.file_name ?? "PDF"}
              </a>
            ) : null}
          </article>
        </div>

        <div className={styles.rightColumn}>
          <article className={styles.panel}>
            <div className={styles.panelTitleRow}>
              <span className={styles.panelIcon}>⚙</span>
              <h2>Configuración del PDF</h2>
            </div>

            <div className={styles.configGrid}>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>
                  <span className={styles.fieldIcon}>🔢</span>
                  Desde capítulo
                </span>
                <input
                  type="number"
                  min={1}
                  max={chapterCount || 1}
                  value={chapterStart}
                  onChange={(event) => setChapterStart(Number(event.target.value))}
                  disabled={!metadata}
                />
              </label>

              <label className={styles.field}>
                <span className={styles.fieldLabel}>
                  <span className={styles.fieldIcon}>📚</span>
                  Hasta capítulo
                </span>
                <input
                  type="number"
                  min={1}
                  max={chapterCount || 1}
                  value={chapterEnd}
                  onChange={(event) => setChapterEnd(Number(event.target.value))}
                  disabled={!metadata}
                />
              </label>

              <label className={styles.field}>
                <span className={styles.fieldLabel}>
                  <span className={styles.fieldIcon}>🌐</span>
                  Idioma
                </span>
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
              className={styles.generateButton}
              disabled={!metadata || creatingJob}
              onClick={handleCreateJob}
            >
              {creatingJob ? "Creando trabajo..." : "Generar PDF"}
              <span className={styles.generateIcon}>🖨</span>
            </button>
          </article>

          <article className={`${styles.panel} ${styles.previewPanel}`}>
            <div className={styles.previewHeader}>
              <div>
                <span className={styles.sectionEyebrow}>NOVELA DETECTADA</span>
              </div>

              <div className={styles.chapterCountPill}>{chapterPill}</div>
            </div>

            <div className={styles.previewGrid}>
              <div className={styles.coverBlock}>
                <div className={styles.coverCard}>
                  {metadata?.cover_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={metadata.cover_url}
                      alt={metadata.title}
                      className={styles.coverImage}
                    />
                  ) : (
                    <div className={styles.coverFallback}>Sin portada</div>
                  )}
                </div>

                <div className={styles.coverMeta}>
                  <h3>{metadata?.title ?? "Sin novela cargada"}</h3>
                  <p>{metadata?.author ?? "Autor desconocido"}</p>

                  <div className={styles.genreList}>
                    {(metadata?.genres.length ? metadata.genres : ["Sin género"]).map(
                      (genre) => (
                        <span key={genre} className={styles.genreChip}>
                          {genre}
                        </span>
                      ),
                    )}
                  </div>
                </div>
              </div>

              <div className={styles.chapterBlock}>
                <div className={styles.chapterTitleRow}>
                  <h3>Capítulos</h3>
                </div>

                <div className={styles.chapterScroller}>
                  {visibleChapters.length ? (
                    visibleChapters.map((chapter) => (
                      <div
                        key={`${chapter.index}-${chapter.title}`}
                        className={styles.chapterRow}
                      >
                        <span className={styles.chapterRowIcon}>▣</span>
                        <span className={styles.chapterRowText}>
                          #{chapter.index} {chapter.title}
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className={styles.chapterEmpty}>
                      Aquí aparecerán los capítulos encontrados.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>

      <footer className={styles.footer}>
        <span>Marca de agua por WynnDev</span>
        <a href="https://github.com/NyoWynn" target="_blank" rel="noreferrer">
          github.com/NyoWynn
        </a>
      </footer>
    </main>
  );
}
