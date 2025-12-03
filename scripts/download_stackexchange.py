#!/usr/bin/env python3
"""
PG Index Agents - Script de descarga Stack Exchange
https://github.com/686f6c61/pg-index-agents

Script interactivo para descargar el data dump de Stack Exchange desde
archive.org. Presenta un menu con opciones de descarga y maneja la
extraccion automatica de archivos .7z.

Opciones de descarga:
    1. Full Stack Overflow: ~30GB comprimido
       Posts, Users, Comments, Votes, Badges, Tags
    2. Stack Overflow Core: ~21GB comprimido
       Solo Posts y Users
    3. DBA Stack Exchange: ~500MB comprimido
       Sitio pequeno ideal para testing
    4. Seleccion personalizada de archivos

Archivos disponibles en archive.org:
    - stackoverflow.com-Posts.7z (~20GB)
    - stackoverflow.com-Users.7z (~1GB)
    - stackoverflow.com-Comments.7z (~6GB)
    - stackoverflow.com-Votes.7z (~3GB)
    - stackoverflow.com-Badges.7z (~300MB)
    - stackoverflow.com-Tags.7z (~5MB)
    - dba.stackexchange.com.7z (~500MB)

Directorio de salida: {proyecto}/data/

Requisitos:
    - wget (opcional, para descargas con resume)
    - p7zip-full (sudo apt install p7zip-full)

Uso:
    python download_stackexchange.py

Siguiente paso:
    python import_to_postgres.py

Autor: 686f6c61
Licencia: MIT
"""

import os
import subprocess
import sys
from pathlib import Path
from urllib.request import urlretrieve
import time

# Base URL for Stack Exchange data dump
# Using the latest dump from archive.org
BASE_URL = "https://archive.org/download/stackexchange"

# Stack Overflow is the main site we want (largest dataset)
# Files to download:
STACKOVERFLOW_FILES = [
    "stackoverflow.com-Posts.7z",       # ~20GB compressed, ~90GB uncompressed
    "stackoverflow.com-Users.7z",        # ~1GB compressed
    "stackoverflow.com-Comments.7z",     # ~6GB compressed
    "stackoverflow.com-Votes.7z",        # ~3GB compressed
    "stackoverflow.com-Badges.7z",       # ~300MB compressed
    "stackoverflow.com-Tags.7z",         # ~5MB compressed
    "stackoverflow.com-PostLinks.7z",    # ~200MB compressed
    "stackoverflow.com-PostHistory.7z",  # ~50GB compressed (optional, very large)
]

# Smaller alternative: Use a smaller Stack Exchange site for testing
SMALL_SITE_FILES = [
    "dba.stackexchange.com.7z",  # Database Administrators - ~500MB, good for testing
]

DATA_DIR = Path(__file__).parent.parent / "data"


def download_file(url: str, dest: Path, desc: str = None) -> bool:
    """Download a file with progress reporting."""
    if dest.exists():
        print(f"  [SKIP] {dest.name} already exists")
        return True

    print(f"  [DOWN] Downloading {desc or dest.name}...")
    print(f"         URL: {url}")

    try:
        # Use wget for better progress and resume support
        result = subprocess.run(
            ["wget", "-c", "-O", str(dest), url],
            check=True
        )
        print(f"  [DONE] {dest.name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [FAIL] Failed to download {dest.name}: {e}")
        return False
    except FileNotFoundError:
        # wget not available, fall back to urllib
        print("  [INFO] wget not found, using Python urllib (slower, no resume)")
        try:
            def progress_hook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = min(100, block_num * block_size * 100 // total_size)
                    mb_done = block_num * block_size / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    print(f"\r         {percent}% ({mb_done:.1f}/{mb_total:.1f} MB)", end="")

            urlretrieve(url, dest, progress_hook)
            print(f"\n  [DONE] {dest.name}")
            return True
        except Exception as e:
            print(f"\n  [FAIL] Failed to download {dest.name}: {e}")
            return False


def extract_7z(archive: Path, dest_dir: Path) -> bool:
    """Extract a 7z archive."""
    print(f"  [EXTR] Extracting {archive.name}...")

    try:
        result = subprocess.run(
            ["7z", "x", "-y", f"-o{dest_dir}", str(archive)],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"  [DONE] Extracted {archive.name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [FAIL] Failed to extract {archive.name}: {e.stderr}")
        return False
    except FileNotFoundError:
        print("  [FAIL] 7z not found. Install with: sudo apt install p7zip-full")
        return False


def main():
    """Main download function."""
    print("=" * 60)
    print("Stack Exchange Data Downloader")
    print("=" * 60)

    # Check for required tools
    print("\n[CHECK] Checking required tools...")

    has_wget = subprocess.run(["which", "wget"], capture_output=True).returncode == 0
    has_7z = subprocess.run(["which", "7z"], capture_output=True).returncode == 0

    if not has_7z:
        print("[ERROR] 7z not found. Install with: sudo apt install p7zip-full")
        sys.exit(1)

    print(f"  wget: {'✓' if has_wget else '✗ (will use slower Python download)'}")
    print(f"  7z:   ✓")

    # Create data directory
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n[INFO] Data directory: {DATA_DIR}")

    # Ask user what to download
    print("\n[MENU] What would you like to download?")
    print("  1. Full Stack Overflow (Posts, Users, Comments, Votes, Badges, Tags)")
    print("     ~30GB compressed, ~150GB uncompressed, 300M+ rows")
    print("  2. Stack Overflow Core (Posts, Users only)")
    print("     ~21GB compressed, ~100GB uncompressed")
    print("  3. DBA Stack Exchange (smaller, good for testing)")
    print("     ~500MB compressed, ~2GB uncompressed")
    print("  4. Custom selection")

    choice = input("\nEnter choice [1-4]: ").strip()

    if choice == "1":
        files = [
            "stackoverflow.com-Posts.7z",
            "stackoverflow.com-Users.7z",
            "stackoverflow.com-Comments.7z",
            "stackoverflow.com-Votes.7z",
            "stackoverflow.com-Badges.7z",
            "stackoverflow.com-Tags.7z",
        ]
    elif choice == "2":
        files = [
            "stackoverflow.com-Posts.7z",
            "stackoverflow.com-Users.7z",
        ]
    elif choice == "3":
        files = ["dba.stackexchange.com.7z"]
    elif choice == "4":
        print("\nAvailable files:")
        all_files = STACKOVERFLOW_FILES + SMALL_SITE_FILES
        for i, f in enumerate(all_files, 1):
            print(f"  {i}. {f}")

        selected = input("Enter file numbers (comma-separated): ").strip()
        indices = [int(x.strip()) - 1 for x in selected.split(",")]
        files = [all_files[i] for i in indices if 0 <= i < len(all_files)]
    else:
        print("Invalid choice")
        sys.exit(1)

    print(f"\n[INFO] Will download {len(files)} file(s)")

    # Download files
    print("\n[DOWNLOAD] Starting downloads...")
    downloaded = []

    for filename in files:
        url = f"{BASE_URL}/{filename}"
        dest = DATA_DIR / filename

        if download_file(url, dest, filename):
            downloaded.append(dest)

    # Extract files
    print("\n[EXTRACT] Extracting archives...")

    for archive in downloaded:
        extract_7z(archive, DATA_DIR)

    # List extracted files
    print("\n[DONE] Extraction complete!")
    print("\nExtracted XML files:")
    for xml_file in sorted(DATA_DIR.glob("*.xml")):
        size_mb = xml_file.stat().st_size / (1024 * 1024)
        print(f"  {xml_file.name}: {size_mb:.1f} MB")

    print("\n[NEXT] Run the import script to load data into PostgreSQL:")
    print("       python scripts/import_to_postgres.py")


if __name__ == "__main__":
    main()
