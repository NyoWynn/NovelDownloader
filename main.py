"""
main.py
Entry point for Novel Downloader.
"""

import sys
import os

# Ensure the app directory is on the path (needed when running as a .exe)
if getattr(sys, "frozen", False):
    # Running as PyInstaller bundle
    os.chdir(sys._MEIPASS)

from gui import run

if __name__ == "__main__":
    run()
