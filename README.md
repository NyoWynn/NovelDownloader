# NovelDownloader

Desktop app for downloading archived web novels from Wayback Machine links and exporting them as polished PDF books.

![NovelDownloader logo](./resources/logo.png)

## What It Does

- Fetches novel metadata and chapter lists from supported archive pages
- Downloads all chapters or a selected range
- Exports a styled PDF with cover, table of contents, headers, and page numbers
- Lets you choose between original text or a Spanish-translated PDF
- Includes a desktop UI built with CustomTkinter

## Highlights

- Clean dark/light theme desktop interface
- Output folder picker
- Progress log and cancel support
- Branded footer and application icon
- Windows executable build with PyInstaller

## Screenshots / Build

The packaged Windows build is published in the project releases as `NovelDownloader.exe`.

## Run From Source

```bash
pip install -r requirements.txt
python main.py
```

## Build The EXE

```bash
python make_icon.py
python -m PyInstaller NovelDownloader.spec --clean --noconfirm
```

The compiled executable will be generated in `dist/NovelDownloader.exe`.

## Project Structure

```text
gui.py               Desktop UI
scraper.py           Chapter and metadata extraction
pdf_generator.py     PDF layout and export
translator.py        Optional Spanish translation layer
main.py              App entry point
resources/           Logos and bundled assets
```

## Tech Stack

- Python 3.11
- CustomTkinter
- Requests
- BeautifulSoup4
- ReportLab
- Pillow
- PyInstaller

## Notes

- Spanish translation depends on an online translation service at download time.
- The repository tracks source code; built binaries belong in GitHub Releases.

## Author

Built by [NyoWynn](https://github.com/NyoWynn)
