"""Finding lifecycle state (acknowledged, in progress, resolved)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from radar.config import FEED, ensure_dirs

FINDINGS_STATE_FILE = FEED / "findings_state.json"
ALERT_LOG_FILE = FEED / "alert_log.json"

VALID_STATUSES = {
    "detected",
    "in_review",
    "auto_alerted",
    "acknowledged",
    "in_progress",
    "resolved",
    "rejected",
    "verified",
}


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data: dict) -> None:
    ensure_dirs()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def get_status(finding_id: str) -> dict:
    return _load(FINDINGS_STATE_FILE).get(finding_id, {})


def set_status(finding_id: str, status: str, **extra) -> dict:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    state = _load(FINDINGS_STATE_FILE)
    entry = {
        **state.get(finding_id, {}),
        "status": status,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        **extra,
    }
    state[finding_id] = entry
    _save(FINDINGS_STATE_FILE, state)
    return entry


def merge_into_gap(gap: dict) -> dict:
    """Overlay persisted lifecycle state onto a gap record."""
    fid = gap.get("finding_id")
    if not fid:
        return gap
    stored = get_status(fid)
    if stored:
        gap = {**gap, **{k: v for k, v in stored.items() if k not in gap or k == "status"}}
    return gap


def log_alert(gap: dict, result: dict) -> None:
    path = ALERT_LOG_FILE
    if path.exists():
        log = json.loads(path.read_text(encoding="utf-8"))
    else:
        log = []
    if not isinstance(log, list):
        log = []
    log.append({
        "finding_id": gap.get("finding_id"),
        "company": gap.get("company"),
        "product": gap.get("product"),
        "regulation": gap.get("regulation"),
        "channel": gap.get("alert", {}).get("channel"),
        "twilio_status": result.get("status"),
        "sent_at": datetime.utcnow().isoformat() + "Z",
        "message_preview": (gap.get("alert", {}).get("message") or "")[:200],
    })
    ensure_dirs()
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
