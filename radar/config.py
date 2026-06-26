"""Paths and environment configuration."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "Dataset"
ECHA_DIR = ROOT / "ECHA"
FEED = ROOT / "feed"
OUTPUT = ROOT / "output"

CACHE_FILE = FEED / "cache.json"
STATE_FILE = FEED / "state.json"
OPTOUTS_FILE = FEED / "optouts.json"
VECTORDB_FILE = FEED / "vectordb.json"
HIL_QUEUE_FILE = FEED / "hil_queue.json"
ROUTER_INDEX_FILE = FEED / "router_index.json"
GAPS_FILE = OUTPUT / "gaps.json"
PARTNERS_FILE = DATASET / "partners.json"
TAXONOMY_FILE = DATASET / "taxonomy.json"
FIXTURE_FILE = DATASET / "regulatory_updates.json"
SOURCES_DOC = DATASET / "SOURCES.md"

EURLEX_WS_URL = "https://eur-lex.europa.eu/EurLexWebService"
DIP_BASE = "https://search.dip.bundestag.de/api/v1"
OPENLEGALDATA_BASE = "https://de.openlegaldata.io/api"


def load_dotenv() -> None:
    """ponytail: naive .env loader — upgrade path is python-dotenv."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def ensure_dirs() -> None:
    FEED.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
