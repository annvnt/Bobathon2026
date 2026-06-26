"""File-based vector store for regulations, taxonomy, and partners."""

from __future__ import annotations

import json
from typing import Any

from radar.config import VECTORDB_FILE, ensure_dirs


def _load() -> dict:
    if not VECTORDB_FILE.exists():
        return {"entries": [], "vocab": {}}
    return json.loads(VECTORDB_FILE.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    ensure_dirs()
    VECTORDB_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def upsert(entry_id: str, kind: str, text: str, vector: list[float], meta: dict | None = None) -> None:
    data = _load()
    record = {
        "id": entry_id,
        "kind": kind,
        "text": text[:500],
        "vector": vector,
        "meta": meta or {},
    }
    data["entries"] = [e for e in data["entries"] if e["id"] != entry_id]
    data["entries"].append(record)
    _save(data)


def get_by_kind(kind: str) -> list[dict]:
    return [e for e in _load()["entries"] if e.get("kind") == kind]


def get_all() -> list[dict]:
    return _load().get("entries", [])


def save_vocab(vocab: dict[str, int]) -> None:
    data = _load()
    data["vocab"] = vocab
    _save(data)


def load_vocab() -> dict[str, int]:
    return _load().get("vocab", {})
