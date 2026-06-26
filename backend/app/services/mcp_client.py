"""Adapter to the real team MCP (`radar.mcp.contract`) living at the repo root.

Maps the MCP's surface — fetch_regulation(labels, countries), check(label),
get_regulations() — onto the two functions the EcoComply pipeline depends on:

    check_updates() -> [{"label", "country", "date"}]
    fetch_regulation(label, country) -> regulation dict (pipeline shape)

The repo root is put on sys.path so `radar` is importable regardless of the
backend's working directory. If radar cannot be imported, callers should fall
back (see gap_analysis).
"""
from __future__ import annotations

import logging
import sys

from ..config import REPO_ROOT

logger = logging.getLogger("ecocomply.mcp")

# Make the repo-root `radar` package importable from the backend.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from radar.mcp import contract  # noqa: E402  (after sys.path tweak)

# Labels whose breach carries the heaviest market/penalty exposure.
_HIGH_SEVERITY = {"Battery", "RoHS", "REACH", "RED", "GPSR", "MDR", "POPs"}


def _severity(label: str) -> str:
    return "high" if label in _HIGH_SEVERITY else "medium"


def _to_update(rec: dict, label: str, country: str) -> dict:
    """Map a hydrated MCP regulation record to the pipeline's regulation dict."""
    text = rec.get("text") or rec.get("summary") or rec.get("title") or ""
    summary = text.strip().replace("\n", " ")
    summary = (summary[:600] + "…") if len(summary) > 600 else summary
    markets = rec.get("countries_affected") or [country]
    return {
        "update_id": rec.get("regulation_text_key") or f"{label}-{country}-{rec.get('reference','')}",
        "regulation_family": label,
        "reference": rec.get("title") or rec.get("reference", ""),
        "title": rec.get("title", ""),
        "summary": summary,
        "text": text,  # full legal body → ingested line-by-line
        "source_url": rec.get("source_url", ""),
        "published_date": (rec.get("stored_at") or "")[:10],
        "deadline_date": None,   # MCP supplies text; deadlines surface via LLM/date extraction
        "effective_date": None,
        "severity": _severity(label),
        "action_required": "",
        "scope": {
            "categories": "all",
            "substances": [],
            "markets": markets,
            "conditions": f"In force for {label} in {', '.join(markets[:3])}"
                          + ("…" if len(markets) > 3 else "") + ".",
        },
    }


def check_updates() -> list[dict]:
    """Labels (EU jurisdiction) the MCP currently holds current regulations for."""
    regs = contract.get_regulations(include_text=False).get("regulations", [])
    seen: set[str] = set()
    out: list[dict] = []
    for r in regs:
        label, country = r.get("category"), r.get("country")
        if country != "EU" or not label or label in seen:
            continue
        seen.add(label)
        out.append({"label": label, "country": country, "date": (r.get("stored_at") or "")[:10]})
    return out


def fetch_regulation(label: str, country: str) -> dict | None:
    """Return the current regulation for a label + market from the MCP."""
    recs = contract.get_regulations(
        category=label, country=country, include_text=True
    ).get("regulations", [])
    if not recs:
        # Not cached yet — ask the MCP to fetch + persist it, then re-read.
        try:
            contract.fetch_regulation([label], [country])
            recs = contract.get_regulations(
                category=label, country=country, include_text=True
            ).get("regulations", [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("MCP fetch_regulation(%s, %s) failed: %s", label, country, exc)
            return None
    if not recs:
        return None
    return _to_update(recs[0], label, country)
