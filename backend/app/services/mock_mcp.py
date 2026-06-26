"""Mock MCP layer  —  THIS IS YOUR TEAMMATE'S DOMAIN (regulation extraction).

The rest of the pipeline only depends on these two function signatures, so the
real MCP server can be dropped in by replacing the bodies below (or pointing
them at the live MCP) with no other code changes:

    check_updates() -> list[{"label": str, "country": str, "date": str}]
        Returns the regulation families that have NEW/changed content since the
        last sync, plus the market they changed in.

    fetch_regulation(label: str, country: str) -> dict
        Returns the full, freshly-extracted regulation record for that family,
        in the shape of Dataset/regulatory_updates.json:
            {update_id, published_date, source, regulation_family, reference,
             title, summary, change_type, effective_date, deadline_date,
             severity, action_required,
             scope: {categories, substances, markets, conditions},
             source_url}

For the hackathon, these read the bundled example feed so the loop produces
real, demoable findings. Replace with live MCP calls when ready.
"""
from __future__ import annotations

import json
from functools import lru_cache

from ..config import settings

# EUR-Lex / source landing pages per family, so every finding can cite a source.
_SOURCE_URLS = {
    "RoHS": "https://eur-lex.europa.eu/eli/dir/2011/65/oj",
    "REACH": "https://echa.europa.eu/candidate-list-table",
    "WEEE": "https://eur-lex.europa.eu/eli/dir/2012/19/oj",
    "Battery": "https://eur-lex.europa.eu/eli/reg/2023/1542/oj",
    "PPWR": "https://eur-lex.europa.eu/eli/reg/2025/40/oj",
    "GPSR": "https://eur-lex.europa.eu/eli/reg/2023/988/oj",
    "RED": "https://eur-lex.europa.eu/eli/dir/2014/53/oj",
    "POPs": "https://eur-lex.europa.eu/eli/reg/2019/1021/oj",
    "ESPR": "https://eur-lex.europa.eu/eli/reg/2024/1781/oj",
}


@lru_cache
def _load_updates() -> list[dict]:
    """Load the example regulatory updates bundled with the challenge dataset."""
    path = settings.dataset_dir / "regulatory_updates.json"
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    # File is {"_comment": ..., "updates": [...]}
    updates = data.get("updates", []) if isinstance(data, dict) else data
    for u in updates:
        u.setdefault("source_url", _SOURCE_URLS.get(u.get("regulation_family", ""), ""))
    return updates


def _index_by_family() -> dict[str, list[dict]]:
    idx: dict[str, list[dict]] = {}
    for u in _load_updates():
        fam = u.get("regulation_family")
        if fam:
            idx.setdefault(fam, []).append(u)
    return idx


# The families we present as "changed this cycle". In the real MCP this comes
# from diffing live sources; here we surface the families with demoable gaps.
_CHANGED_THIS_CYCLE = [
    {"label": "Battery", "country": "EU"},
    {"label": "RoHS", "country": "EU"},
    {"label": "REACH", "country": "EU"},
]


def check_updates() -> list[dict]:
    """Return the labels (families) that have new updates this cycle."""
    idx = _index_by_family()
    out = []
    for item in _CHANGED_THIS_CYCLE:
        if item["label"] in idx:
            latest = max(idx[item["label"]], key=lambda u: u.get("published_date", ""))
            out.append({
                "label": item["label"],
                "country": item["country"],
                "date": latest.get("published_date", ""),
            })
    return out


def fetch_regulation(label: str, country: str) -> dict | None:
    """Return the freshly-extracted regulation record for a family + market."""
    idx = _index_by_family()
    candidates = idx.get(label, [])
    if not candidates:
        return None

    def in_market(u: dict) -> bool:
        markets = u.get("scope", {}).get("markets", [])
        return country in markets or "EU" in markets

    scoped = [u for u in candidates if in_market(u)] or candidates
    # Prefer the most recently published, non-correction entry.
    scoped.sort(
        key=lambda u: (u.get("change_type") != "correction", u.get("published_date", "")),
        reverse=True,
    )
    return scoped[0]
