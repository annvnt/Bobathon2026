"""Portfolio compliance catalog — all partners.csv streams fetchable and browsable."""

from __future__ import annotations

import csv
import json
from typing import Any

from radar.compliance.jurisdictions import expand_jurisdictions
from radar.config import DATASET, PARTNERS_FILE
from radar.mcp import label_regs
from radar.mcp.regulation_ops import fetch_regulation

DEFAULT_CATALOG_COUNTRIES = ["EU", "DE"]


def _split_streams(raw: str) -> list[str]:
    if not raw:
        return []
    parts: list[str] = []
    for chunk in raw.replace("|", ",").replace(";", ",").split(","):
        s = chunk.strip()
        if s:
            parts.append(s)
    return parts


def streams_from_partners_csv() -> list[str]:
    path = DATASET / "partners.csv"
    if not path.exists():
        return list(label_regs.PORTFOLIO_COMPLIANCE_STREAMS)
    found: set[str] = set()
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for stream in _split_streams(row.get("compliance_streams") or ""):
                found.add(stream)
    return sorted(found)


def streams_from_partners_json() -> list[str]:
    if not PARTNERS_FILE.exists():
        return []
    data = json.loads(PARTNERS_FILE.read_text(encoding="utf-8"))
    found: set[str] = set()
    for partner in data.get("partners", []):
        for product in partner.get("products", []):
            for stream in product.get("compliance_streams") or []:
                if stream and str(stream).strip():
                    found.add(str(stream).strip())
    return sorted(found)


def portfolio_streams() -> list[str]:
    """Unique compliance_streams from partners data (csv preferred, then json)."""
    from_csv = streams_from_partners_csv()
    if from_csv:
        return from_csv
    from_json = streams_from_partners_json()
    if from_json:
        return from_json
    return list(label_regs.PORTFOLIO_COMPLIANCE_STREAMS)


def catalog_status(countries: list[str] | None = None) -> dict[str, Any]:
    countries_norm = sorted({c.strip().upper() for c in (countries or DEFAULT_CATALOG_COUNTRIES) if c})
    jurisdictions = [j for j in expand_jurisdictions(countries_norm) if j in ("EU", "DE")]
    stored = label_regs.get_regulations(include_text=False).get("regulations", [])
    streams = portfolio_streams()
    by_stream: dict[str, dict[str, Any]] = {}
    for stream in streams:
        entries: list[dict[str, Any]] = []
        missing: list[dict[str, str]] = []
        skipped_de: list[str] = []
        for jur in jurisdictions:
            if jur == "DE" and not label_regs.should_fetch_de(stream):
                skipped_de.append("DE (EU transposition — EU CELEX only)")
                continue
            hits = [
                e for e in stored
                if e.get("category") == stream and e.get("country") == jur
            ]
            if hits:
                entries.extend(hits)
            else:
                missing.append({"label": stream, "country": jur})
        by_stream[stream] = {
            "stream": stream,
            "stored_count": len(entries),
            "entries": entries,
            "missing": missing,
            "skipped_de_transposition": skipped_de,
            "complete": not missing,
        }
    return {
        "streams": streams,
        "countries": countries_norm,
        "jurisdictions": jurisdictions,
        "by_stream": by_stream,
        "total_streams": len(streams),
        "complete": all(v["complete"] for v in by_stream.values()),
    }


def fetch_portfolio_catalog(
    countries: list[str] | None = None,
    *,
    save: bool = True,
) -> dict[str, Any]:
    """Fetch and persist EU + DE regulations for every portfolio compliance stream."""
    streams = portfolio_streams()
    countries_norm = sorted({c.strip().upper() for c in (countries or DEFAULT_CATALOG_COUNTRIES) if c})
    fetched = fetch_regulation(
        streams,
        countries_norm,
        product_id="_catalog",
        save=save,
    )
    pruned = label_regs.prune_de_transposition_library() if save else 0
    status = catalog_status(countries_norm)
    return {
        "streams": streams,
        "countries": countries_norm,
        "saved": save,
        "fetched_count": fetched.get("count", 0),
        "pruned_de_transposition": pruned,
        "catalog": status,
        **{k: v for k, v in fetched.items() if k not in ("streams", "countries")},
    }
