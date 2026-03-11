"""
gui.py
Desktop GUI for the Novel Downloader using CustomTkinter.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from pdf_generator import generate_pdf
from scraper import ChapterInfo, NovelMetadata, NovelScraper
from translator import translate_text_bundle

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_BG = ("#EEF2F8", "#141420")
SURFACE_BG = ("#FFFFFF", "#1E1E2E")
CARD_BG = ("#E7ECF5", "#252535")
SUBTLE_BG = ("#DCE3EF", "#2D2D42")
TEXT_PRIMARY = ("#172033", "#E8E8F0")
TEXT_MUTED = ("#5A6478", "#9A9AB7")
BORDER = ("#C3CDDB", "#4A4A67")
ACCENT = ("#2E6DBF", "#4A90D9")
ACCENT_HOVER = ("#245AA2", "#3A7BC1")
SUCCESS = "#4CAF84"
ERROR = "#E05555"
WARNING = "#E0A055"
LOGO_SIZE = (34, 34)
WATERMARK_SIZE = (88, 22)
GITHUB_URL = "https://github.com/NyoWynn"


def _resource_path(*parts: str) -> Path:
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_dir.joinpath(*parts)


def _load_image(path: Path, size: tuple[int, int]) -> ctk.CTkImage | None:
    try:
        image = Image.open(path)
        return ctk.CTkImage(light_image=image, dark_image=image, size=size)
    except Exception:
        return None


class NovelDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Novel Downloader")
        self.geometry("860x840")
        self.minsize(760, 700)
        self.configure(fg_color=APP_BG)

        self._metadata: NovelMetadata | None = None
        self._stop_event = threading.Event()
        self._working = False
        self._output_dir = str(Path.home() / "Documents")
        self._dl_mode = tk.StringVar(value="all")
        self._language_mode = tk.StringVar(value="original")
        self._app_logo = _load_image(_resource_path("resources", "logo.png"), LOGO_SIZE)
        self._watermark_logo = _load_image(
            _resource_path("resources", "wynnDevLogo.png"),
            WATERMARK_SIZE,
        )

        _set_icon(self)
        self._build_ui()
        self._sync_theme_button()
        self._log("Bienvenido a Novel Downloader", color=SUCCESS)
        self._log(
            "Pega el link de Wayback Machine de una novela y presiona Obtener info."
        )

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self, fg_color=SURFACE_BG, corner_radius=0, height=82)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        title_wrap = ctk.CTkFrame(header, fg_color="transparent")
        title_wrap.grid(row=0, column=0, padx=22, pady=18, sticky="w")

        logo_label = ctk.CTkLabel(
            title_wrap,
            text="",
            image=self._app_logo,
            width=40,
        )
        logo_label.pack(side="left", padx=(0, 10))

        title_lbl = ctk.CTkLabel(
            title_wrap,
            text="Novel Downloader",
            font=ctk.CTkFont("Helvetica", 23, "bold"),
            text_color=TEXT_PRIMARY,
        )
        title_lbl.pack(side="left")

        self._theme_btn = ctk.CTkButton(
            header,
            width=108,
            height=34,
            fg_color="transparent",
            border_color=BORDER,
            border_width=1,
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._toggle_theme,
        )
        self._theme_btn.grid(row=0, column=1, padx=(0, 20), pady=20)

        url_card = ctk.CTkFrame(self, fg_color=SURFACE_BG, corner_radius=12)
        url_card.grid(row=1, column=0, padx=20, pady=(16, 0), sticky="ew")
        url_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            url_card,
            text="URL de la novela:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=(20, 8), pady=(16, 4), sticky="w")

        self._url_entry = ctk.CTkEntry(
            url_card,
            placeholder_text=(
                "https://web.archive.org/web/20250501021121/"
                "https://lunarletters.com/manga/mery-psycho/"
            ),
            font=ctk.CTkFont(size=11),
            height=40,
            corner_radius=8,
            fg_color=CARD_BG,
            border_color=ACCENT,
            text_color=TEXT_PRIMARY,
        )
        self._url_entry.grid(
            row=1, column=0, columnspan=2, padx=20, pady=(0, 4), sticky="ew"
        )

        btn_row = ctk.CTkFrame(url_card, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=2, padx=20, pady=(4, 16), sticky="w")

        self._fetch_btn = ctk.CTkButton(
            btn_row,
            text="Obtener info",
            height=36,
            width=150,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._on_fetch,
        )
        self._fetch_btn.pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            btn_row,
            text="Pegar",
            height=36,
            width=90,
            fg_color=CARD_BG,
            text_color=TEXT_MUTED,
            hover_color=SUBTLE_BG,
            border_width=1,
            border_color=BORDER,
            command=self._paste_url,
        ).pack(side="left")

        self._info_card = ctk.CTkFrame(self, fg_color=SURFACE_BG, corner_radius=12)
        self._info_card.grid(row=2, column=0, padx=20, pady=(12, 0), sticky="ew")
        self._info_card.grid_columnconfigure(1, weight=1)

        info_left = ctk.CTkFrame(self._info_card, fg_color="transparent")
        info_left.grid(row=0, column=0, padx=20, pady=16, sticky="nw")

        ctk.CTkLabel(
            info_left,
            text="Titulo:",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, sticky="w", pady=2)
        self._lbl_title = ctk.CTkLabel(
            info_left,
            text="-",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=13, weight="bold"),
            wraplength=380,
        )
        self._lbl_title.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=2)

        ctk.CTkLabel(
            info_left,
            text="Autor:",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, sticky="w", pady=2)
        self._lbl_author = ctk.CTkLabel(
            info_left,
            text="-",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=11),
        )
        self._lbl_author.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=2)

        ctk.CTkLabel(
            info_left,
            text="Capitulos:",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).grid(row=2, column=0, sticky="w", pady=2)
        self._lbl_chapters = ctk.CTkLabel(
            info_left,
            text="-",
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=11),
        )
        self._lbl_chapters.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=2)

        opts = ctk.CTkFrame(self._info_card, fg_color=CARD_BG, corner_radius=10)
        opts.grid(row=0, column=1, padx=(0, 20), pady=16, sticky="nsew")
        opts.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            opts,
            text="Opciones de descarga",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, pady=(12, 6), padx=14, sticky="w")

        ctk.CTkRadioButton(
            opts,
            text="Todos los capitulos",
            variable=self._dl_mode,
            value="all",
            command=self._on_mode_change,
            text_color=TEXT_PRIMARY,
            border_color=BORDER,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
        ).grid(row=1, column=0, columnspan=3, padx=14, pady=2, sticky="w")
        ctk.CTkRadioButton(
            opts,
            text="Rango:",
            variable=self._dl_mode,
            value="range",
            command=self._on_mode_change,
            text_color=TEXT_PRIMARY,
            border_color=BORDER,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
        ).grid(row=2, column=0, padx=14, pady=2, sticky="w")

        range_frame = ctk.CTkFrame(opts, fg_color="transparent")
        range_frame.grid(row=3, column=0, columnspan=3, padx=14, pady=(0, 8), sticky="w")

        ctk.CTkLabel(
            range_frame,
            text="Del cap.",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).pack(side="left")
        self._from_entry = ctk.CTkEntry(
            range_frame,
            width=55,
            height=28,
            state="disabled",
            placeholder_text="1",
            fg_color=SURFACE_BG,
            border_color=BORDER,
            text_color=TEXT_PRIMARY,
        )
        self._from_entry.pack(side="left", padx=6)
        ctk.CTkLabel(
            range_frame,
            text="al",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).pack(side="left")
        self._to_entry = ctk.CTkEntry(
            range_frame,
            width=55,
            height=28,
            state="disabled",
            placeholder_text="fin",
            fg_color=SURFACE_BG,
            border_color=BORDER,
            text_color=TEXT_PRIMARY,
        )
        self._to_entry.pack(side="left", padx=6)

        ctk.CTkLabel(
            opts,
            text="Idioma del PDF",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=4, column=0, columnspan=3, padx=14, pady=(6, 2), sticky="w")

        language_row = ctk.CTkFrame(opts, fg_color="transparent")
        language_row.grid(row=5, column=0, columnspan=3, padx=14, pady=(0, 8), sticky="w")

        ctk.CTkRadioButton(
            language_row,
            text="Original",
            variable=self._language_mode,
            value="original",
            text_color=TEXT_PRIMARY,
            border_color=BORDER,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(
            language_row,
            text="Espanol",
            variable=self._language_mode,
            value="es",
            text_color=TEXT_PRIMARY,
            border_color=BORDER,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
        ).pack(side="left")

        out_frame = ctk.CTkFrame(opts, fg_color="transparent")
        out_frame.grid(row=6, column=0, columnspan=3, padx=14, pady=(4, 6), sticky="ew")
        out_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            out_frame,
            text="Carpeta de salida:",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        self._out_dir_lbl = ctk.CTkLabel(
            out_frame,
            text=self._output_dir,
            text_color=ACCENT,
            font=ctk.CTkFont(size=10),
            wraplength=260,
        )
        self._out_dir_lbl.grid(row=1, column=0, sticky="w")
        ctk.CTkButton(
            out_frame,
            text="Abrir",
            width=48,
            height=28,
            command=self._pick_folder,
            fg_color=SUBTLE_BG,
            hover_color=CARD_BG,
            text_color=TEXT_PRIMARY,
        ).grid(row=1, column=1, padx=(6, 0))

        dl_row = ctk.CTkFrame(self._info_card, fg_color="transparent")
        dl_row.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 16), sticky="ew")
        dl_row.grid_columnconfigure(0, weight=1)

        self._progress = ctk.CTkProgressBar(
            dl_row,
            mode="determinate",
            height=12,
            corner_radius=6,
            progress_color=ACCENT,
            fg_color=CARD_BG,
        )
        self._progress.set(0)
        self._progress.grid(row=0, column=0, sticky="ew", pady=(0, 8), padx=(0, 12))

        self._progress_lbl = ctk.CTkLabel(
            dl_row,
            text="",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=10),
        )
        self._progress_lbl.grid(row=1, column=0, sticky="w")

        btn_dl_row = ctk.CTkFrame(self._info_card, fg_color="transparent")
        btn_dl_row.grid(row=2, column=0, columnspan=2, padx=20, pady=(0, 16), sticky="ew")

        self._download_btn = ctk.CTkButton(
            btn_dl_row,
            text="Descargar PDF",
            height=42,
            width=200,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="white",
            fg_color=SUCCESS,
            hover_color="#3A9D6A",
            state="disabled",
            command=self._on_download,
        )
        self._download_btn.pack(side="left", padx=(0, 12))

        self._stop_btn = ctk.CTkButton(
            btn_dl_row,
            text="Cancelar",
            height=42,
            width=110,
            text_color="white",
            fg_color=ERROR,
            hover_color="#C04444",
            state="disabled",
            command=self._on_cancel,
        )
        self._stop_btn.pack(side="left")

        log_card = ctk.CTkFrame(self, fg_color=SURFACE_BG, corner_radius=12)
        log_card.grid(row=3, column=0, padx=20, pady=(12, 12), sticky="nsew")
        log_card.grid_rowconfigure(1, weight=1)
        log_card.grid_columnconfigure(0, weight=1)

        log_hdr = ctk.CTkFrame(log_card, fg_color="transparent")
        log_hdr.grid(row=0, column=0, padx=20, pady=(12, 4), sticky="ew")
        log_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_hdr,
            text="Registro de actividad",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            log_hdr,
            text="Limpiar",
            width=80,
            height=24,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=10),
            command=self._clear_log,
        ).grid(row=0, column=1)

        self._log_box = ctk.CTkTextbox(
            log_card,
            font=ctk.CTkFont("Courier", 11),
            fg_color=CARD_BG,
            text_color=TEXT_PRIMARY,
            wrap="word",
            activate_scrollbars=True,
        )
        self._log_box.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self._log_box.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent", height=34)
        footer.grid(row=4, column=0, padx=20, pady=(0, 14), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        footer_inner = ctk.CTkFrame(footer, fg_color="transparent")
        footer_inner.grid(row=0, column=0)

        ctk.CTkLabel(
            footer_inner,
            text="",
            image=self._watermark_logo,
            width=WATERMARK_SIZE[0],
        ).pack(side="left", padx=(0, 8))
        footer_link = ctk.CTkLabel(
            footer_inner,
            text="@NyoWynn",
            cursor="hand2",
            text_color=ACCENT,
            font=ctk.CTkFont(size=11, underline=True),
        )
        footer_link.pack(side="left")
        footer_link.bind("<Button-1>", lambda _event: webbrowser.open(GITHUB_URL))

    def _on_fetch(self):
        url = self._url_entry.get().strip()
        if not url:
            messagebox.showwarning("URL vacia", "Por favor ingresa una URL.")
            return
        if self._working:
            return

        self._set_working(True, fetch_only=True)
        self._log(f"\n-- Obteniendo informacion: {url[:70]}...", color=ACCENT[1])
        threading.Thread(target=self._fetch_thread, args=(url,), daemon=True).start()

    def _fetch_thread(self, url: str):
        try:
            scraper = NovelScraper(
                delay=1.0,
                progress_callback=lambda msg: self.after(0, lambda m=msg: self._log(m)),
            )
            meta = scraper.get_novel_metadata(url)
            self.after(0, lambda: self._on_fetch_done(meta))
        except Exception as exc:
            self.after(0, lambda: self._on_fetch_error(str(exc)))

    def _on_fetch_done(self, meta: NovelMetadata):
        self._metadata = meta
        self._lbl_title.configure(text=meta.title or "Sin titulo")
        self._lbl_author.configure(text=meta.author or "Desconocido")
        self._lbl_chapters.configure(text=f"{len(meta.chapters)} capitulos encontrados")
        self._log(
            f"OK Novela encontrada: '{meta.title}' - {len(meta.chapters)} capitulos",
            color=SUCCESS,
        )
        self._to_entry.configure(placeholder_text=str(len(meta.chapters)))
        self._set_working(False)
        if meta.chapters:
            self._download_btn.configure(state="normal")

    def _on_fetch_error(self, err: str):
        self._log(f"Error al obtener info: {err}", color=ERROR)
        self._set_working(False)

    def _on_download(self):
        if self._working or not self._metadata:
            return

        chapters = self._get_selected_chapters()
        if not chapters:
            messagebox.showwarning("Sin capitulos", "No hay capitulos para descargar.")
            return

        self._stop_event.clear()
        self._set_working(True, fetch_only=False)
        self._progress.set(0)
        self._progress_lbl.configure(text=f"0 / {len(chapters)} capitulos")
        self._log(
            f"\n-- Iniciando descarga de {len(chapters)} capitulos...",
            color=ACCENT[1],
        )

        threading.Thread(
            target=self._download_thread,
            args=(chapters, self._language_mode.get()),
            daemon=True,
        ).start()

    def _download_thread(self, chapters: list[ChapterInfo], output_language: str):
        def chapter_progress(current, total, title):
            pct = current / total
            label = f"{current}/{total} - {title[:50]}"
            self.after(0, lambda: self._update_progress(pct, label))

        def log_cb(msg: str):
            self.after(0, lambda m=msg: self._log(m))

        try:
            scraper = NovelScraper(delay=1.2, progress_callback=log_cb)
            contents = scraper.download_chapters(
                chapters,
                per_chapter_callback=chapter_progress,
                stop_event=self._stop_event,
            )

            if self._stop_event.is_set():
                self.after(0, lambda: self._log("Descarga cancelada.", color=WARNING))
                self.after(0, lambda: self._set_working(False))
                return

            description = self._metadata.description
            if output_language == "es":
                log_cb("Traduciendo contenido al espanol...")
                description, contents = translate_text_bundle(
                    description=description,
                    chapters=contents,
                    progress_callback=log_cb,
                )

            safe_title = _safe_filename(self._metadata.title or "novela")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            suffix = "_es" if output_language == "es" else ""
            out_path = os.path.join(
                self._output_dir,
                f"{safe_title}{suffix}_{timestamp}.pdf",
            )

            self.after(
                0,
                lambda: self._log(
                    "Generando PDF... esto puede tardar un momento.",
                    color=ACCENT[1],
                ),
            )

            generate_pdf(
                output_path=out_path,
                novel_title=self._metadata.title,
                author=self._metadata.author,
                description=description,
                genres=self._metadata.genres,
                chapters=contents,
                progress_callback=log_cb,
            )

            self.after(0, lambda p=out_path: self._on_download_done(p))
        except Exception as exc:
            self.after(0, lambda e=str(exc): self._on_download_error(e))

    def _on_download_done(self, out_path: str):
        self._progress.set(1.0)
        self._progress_lbl.configure(text="Completado")
        self._log(f"\nPDF listo:\n   {out_path}", color=SUCCESS)
        self._set_working(False)

        if messagebox.askyesno(
            "Descarga completa",
            f"PDF generado exitosamente.\n\n{out_path}\n\nAbrir la carpeta de destino?",
        ):
            os.startfile(os.path.dirname(out_path))

    def _on_download_error(self, err: str):
        self._log(f"Error durante la descarga: {err}", color=ERROR)
        self._set_working(False)

    def _on_cancel(self):
        self._stop_event.set()
        self._log(
            "Cancelando... el capitulo actual terminara antes de detenerse.",
            color=WARNING,
        )

    def _get_selected_chapters(self) -> list[ChapterInfo]:
        if not self._metadata:
            return []

        chapters = self._metadata.chapters
        if self._dl_mode.get() == "all":
            return chapters

        try:
            from_val = int(self._from_entry.get() or 1)
            to_val = int(self._to_entry.get() or len(chapters))
        except ValueError:
            messagebox.showwarning("Rango invalido", "Ingresa numeros validos.")
            return []

        from_idx = max(0, from_val - 1)
        to_idx = min(len(chapters), to_val)
        return chapters[from_idx:to_idx]

    def _on_mode_change(self):
        state = "normal" if self._dl_mode.get() == "range" else "disabled"
        self._from_entry.configure(state=state)
        self._to_entry.configure(state=state)

    def _set_working(self, working: bool, fetch_only: bool = False):
        self._working = working
        state = "disabled" if working else "normal"
        self._fetch_btn.configure(state=state)
        self._url_entry.configure(state=state)
        if not fetch_only:
            self._download_btn.configure(state="disabled" if working else "normal")
            self._stop_btn.configure(state="normal" if working else "disabled")
        else:
            self._stop_btn.configure(state="disabled")

    def _update_progress(self, pct: float, label: str):
        self._progress.set(pct)
        self._progress_lbl.configure(text=label)

    def _pick_folder(self):
        folder = filedialog.askdirectory(
            initialdir=self._output_dir,
            title="Seleccionar carpeta de salida",
        )
        if folder:
            self._output_dir = folder
            self._out_dir_lbl.configure(text=folder)

    def _paste_url(self):
        try:
            txt = self.clipboard_get()
            self._url_entry.delete(0, "end")
            self._url_entry.insert(0, txt)
        except Exception:
            pass

    def _toggle_theme(self):
        current = ctk.get_appearance_mode().lower()
        ctk.set_appearance_mode("light" if current == "dark" else "dark")
        self._sync_theme_button()

    def _sync_theme_button(self):
        if ctk.get_appearance_mode().lower() == "dark":
            self._theme_btn.configure(text="Modo claro")
        else:
            self._theme_btn.configure(text="Modo oscuro")

    def _log(self, msg: str, color: str | None = None):
        self._log_box.configure(state="normal")
        if color:
            tag = f"color_{color.replace('#', '')}"
            self._log_box.tag_config(tag, foreground=color)
            self._log_box.insert("end", msg + "\n", tag)
        else:
            self._log_box.insert("end", msg + "\n")
        self._log_box.configure(state="disabled")
        self._log_box.see("end")

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")


def _safe_filename(text: str) -> str:
    import re

    safe = re.sub(r'[\\/*?:"<>|]', "", text)
    safe = safe.strip().replace(" ", "_")
    return safe[:80] or "novela"


def _set_icon(window):
    try:
        png_path = _resource_path("resources", "logo.png")
        if png_path.exists():
            icon = Image.open(png_path)
            photo = tk.PhotoImage(file=str(png_path))
            window.iconphoto(True, photo)
            window._icon_photo = photo
            window._icon_image = icon

        ico_path = Path(__file__).resolve().parent / "icon.ico"
        if ico_path.exists():
            window.iconbitmap(str(ico_path))
    except Exception:
        pass


def run():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    app = NovelDownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    run()
