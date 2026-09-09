#!/usr/bin/env python3
"""
SpyPoint Photo Downloader für Home Assistant
=============================================

Lädt neue Fotos von SpyPoint herunter und speichert sie in einem lokalen
Ordner. Dieser Ordner kann per Docker-Volume in den Home-Assistant-Container
eingebunden werden, sodass die Fotos im Media-Browser auftauchen.

Pflegt zusätzlich einen Unterordner "latest" mit den 7 neuesten Fotos unter
festen Dateinamen (latest_1.jpg = neuestes ... latest_7.jpg), damit feste
local_file-Kamera-Entities in Home Assistant darauf zeigen können.

Gedacht zum Ausführen per Cronjob (z.B. alle 30 Minuten). Die Benachrichtigung
bei neuen Fotos übernimmt eine Home-Assistant-Automation (folder_watcher),
nicht dieses Script.

Zugangsdaten werden NICHT im Script gespeichert, sondern über
Umgebungsvariablen übergeben:
    SPYPOINT_USERNAME
    SPYPOINT_PASSWORD

Installation (auf dem Pi):
    python3 -m venv ~/spypoint-env
    source ~/spypoint-env/bin/activate
    pip install pyspypoint requests
"""

import hashlib
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
import spypoint

# ---------------------------------------------------------------------------
# Konfiguration - bei Bedarf anpassen
# ---------------------------------------------------------------------------

# Zielordner für die Fotos (später per Docker-Volume in HA einbinden)
DOWNLOAD_DIR = Path.home() / "spypoint-photos"

# Unterordner mit festen Dateinamen für die 7 neuesten Fotos (fürs Dashboard)
LATEST_DIR = DOWNLOAD_DIR / "latest"
LATEST_COUNT = 7

# Wie viele der neuesten Fotos insgesamt geprüft werden sollen
PHOTO_LIMIT = 50

# Datei mit bereits heruntergeladenen Dateinamen (verhindert Doppel-Downloads)
DOWNLOADED_LOG = DOWNLOAD_DIR / ".downloaded.json"

LOG_FILE = DOWNLOAD_DIR / "spypoint_download.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def setup_logging() -> logging.Logger:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("spypoint_downloader")


def load_downloaded(log: logging.Logger) -> set:
    if DOWNLOADED_LOG.exists():
        try:
            with open(DOWNLOADED_LOG, "r") as f:
                return set(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Konnte %s nicht lesen (%s), starte mit leerer Liste.", DOWNLOADED_LOG, e)
    return set()


def save_downloaded(seen: set) -> None:
    with open(DOWNLOADED_LOG, "w") as f:
        json.dump(sorted(seen), f)


def photo_key(url: str) -> str:
    """Eindeutiger Schlüssel für ein Foto, basierend auf seiner URL."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def filename_for(url: str) -> str:
    """Leitet einen Dateinamen aus der URL ab, mit Fallback auf einen Hash."""
    path_name = os.path.basename(urlparse(url).path)
    if path_name and "." in path_name:
        return path_name
    return f"{photo_key(url)}.jpg"


def capture_sort_key(path: Path) -> datetime:
    """Zeitstempel aus dem Dateinamen (z.B. PICT1008_202609090600xxxxx.jpg
    -> 2026-09-09 06:00) fuer die chronologische Sortierung. Dateien ohne
    erkennbaren Zeitstempel (z.B. Hash-Fallback-Namen) sortieren ans Ende,
    damit sie nie faelschlich als "neuestes Foto" gelten."""
    match = re.search(r"_(\d{12})", path.stem)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d%H%M")
        except ValueError:
            pass
    return datetime.min


def update_latest(log: logging.Logger) -> None:
    """Kopiert die 7 neuesten Fotos aus DOWNLOAD_DIR nach LATEST_DIR unter
    festen Namen latest_1.jpg (neuestes) bis latest_7.jpg (aeltestes davon).
    Sortiert NACH DEM IM DATEINAMEN ENTHALTENEN AUFNAHME-/UPLOAD-ZEITSTEMPEL,
    NICHT nach der Datei-mtime auf der Platte: die Download-Reihenfolge
    (mtime) entspricht nicht der inhaltlichen Aktualitaet, weil beim
    Herunterladen zuerst die neuesten Fotos an der Reihe sind und dadurch
    die zuletzt heruntergeladenen (= inhaltlich aeltesten) Fotos die
    juengste mtime bekommen wuerden."""
    all_photos = [
        p for p in DOWNLOAD_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg")
    ]
    all_photos.sort(key=capture_sort_key, reverse=True)
    newest = all_photos[:LATEST_COUNT]

    for i in range(1, LATEST_COUNT + 1):
        target = LATEST_DIR / f"latest_{i}.jpg"
        if i <= len(newest):
            try:
                shutil.copy2(newest[i - 1], target)
            except OSError as e:
                log.error("Konnte %s nicht nach %s kopieren: %s", newest[i - 1], target, e)
        elif target.exists():
            target.unlink()

    log.info("Latest-Ordner aktualisiert (%d von %d Plätzen befüllt).", min(len(newest), LATEST_COUNT), LATEST_COUNT)


def main() -> int:
    log = setup_logging()

    username = os.environ.get("SPYPOINT_USERNAME")
    password = os.environ.get("SPYPOINT_PASSWORD")
    if not username or not password:
        log.error("SPYPOINT_USERNAME und/oder SPYPOINT_PASSWORD sind nicht gesetzt.")
        return 1

    log.info("Melde mich bei SpyPoint an...")
    try:
        client = spypoint.Client(username, password)
    except Exception as e:
        log.error("Login fehlgeschlagen: %s", e)
        return 1

    try:
        cameras = client.cameras()
    except Exception as e:
        log.error("Konnte Kameras nicht abrufen: %s", e)
        return 1

    log.info("Gefundene Kameras: %d", len(cameras) if cameras else 0)

    try:
        photos = client.photos(cameras, limit=PHOTO_LIMIT)
    except Exception as e:
        log.error("Konnte Fotos nicht abrufen: %s", e)
        return 1

    log.info("Abgerufene Fotos (geprüft): %d", len(photos) if photos else 0)

    downloaded = load_downloaded(log)
    new_count = 0

    for photo in photos:
        try:
            url = photo.url()
        except Exception as e:
            log.error("Konnte URL für ein Foto nicht lesen: %s", e)
            continue

        # Dedup anhand des Dateinamens (aus dem URL-Pfad), NICHT anhand der
        # ganzen URL: SpyPoint hängt ein zeitlich begrenztes Signatur-Token
        # als Query-Parameter an, das sich bei jeder Abfrage ändert, auch
        # wenn es dasselbe Foto ist. Der Dateiname selbst bleibt stabil.
        filename = filename_for(url)
        filepath = DOWNLOAD_DIR / filename

        if filename in downloaded or filepath.exists():
            continue

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(resp.content)
            downloaded.add(filename)
            new_count += 1
            log.info("Heruntergeladen: %s", filepath.name)
        except Exception as e:
            log.error("Download fehlgeschlagen für %s: %s", url, e)

    save_downloaded(downloaded)

    # "latest"-Ordner erst NACH dem Download-Durchlauf aktualisieren, damit
    # er immer die tatsächlich neuesten 7 Fotos enthält.
    update_latest(log)

    log.info("Fertig. %d neue(s) Foto(s) heruntergeladen.", new_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
