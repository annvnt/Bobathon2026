"""Human-in-the-loop queue for low-confidence router matches."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from radar.config import HIL_QUEUE_FILE, ensure_dirs

CONFIDENCE_THRESHOLD = 60.0


def _load() -> list[dict]:
    if not HIL_QUEUE_FILE.exists():
        return []
    return json.loads(HIL_QUEUE_FILE.read_text(encoding="utf-8"))


def _save(items: list[dict]) -> None:
    ensure_dirs()
    HIL_QUEUE_FILE.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")


def enqueue(update: dict, matches: list[dict], reason: str = "low_confidence") -> None:
    conf = update.get("router_confidence", 0)
    if conf >= CONFIDENCE_THRESHOLD:
        return
    items = _load()
    item = {
        "id": update.get("update_id") or update.get("dedup_key"),
        "title": update.get("title"),
        "source": update.get("source"),
        "router_matches": matches,
        "router_confidence": conf,
        "reason": reason,
        "status": "pending",
        "queued_at": datetime.utcnow().isoformat() + "Z",
    }
    items = [i for i in items if i.get("id") != item["id"]]
    items.append(item)
    _save(items)


def list_pending() -> list[dict]:
    return [i for i in _load() if i.get("status") == "pending"]


def approve(item_id: str, chosen_match_id: str | None = None) -> dict | None:
    items = _load()
    for item in items:
        if item.get("id") == item_id:
            item["status"] = "approved"
            item["chosen_match_id"] = chosen_match_id
            item["reviewed_at"] = datetime.utcnow().isoformat() + "Z"
            _save(items)
            return item
    return None
