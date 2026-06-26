"""
Team MCP contract — fetch_regulation() and check_label().

  fetch_regulation(labels, countries)  → resolve + save EU/DE laws to feed/label_regulations/
  check_label(label, since)            → recent OJ / cache hits for that compliance label
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from radar.compliance import taxonomy
from radar.ingest import oj_rss, translate
from radar.ingest.fetch import load_cache
from radar.mcp import label_regs

DEFAULT_CHECK_DAYS = 90


def _celex_variants(celex: str) -> set[str]:
    celex = celex.strip()
    variants = {celex, celex.replace("CELEX ", "")}
    normalized = celex.replace("CELEX ", "")
    if len(normalized) >= 10 and normalized[0] == "3":
        year = normalized[1:5]
        kind = normalized[5]
        num = normalized[6:].lstrip("0") or normalized[6:]
        variants.add(f"{year}/{num}")
        variants.add(f"{year}{kind}{num}")
        if kind == "R":
            variants.add(f"{year}/{num}")  # regulation number style
    return {v.lower() for v in variants if v}


def _label_keywords(label: str) -> list[str]:
    label_l = label.strip().lower()
    terms = [label_l] if label_l else []
    for kw in taxonomy.FAMILY_KEYWORDS.get(label, []):
        if len(kw) >= 3:
            terms.append(kw.lower())
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _blob(hit: dict[str, Any]) -> str:
    return " ".join(
        str(hit.get(k) or "")
        for k in ("title", "summary", "reference", "celex", "description")
    ).lower()


def _oj_hit_matches_label(hit: dict[str, Any], label: str, anchor_celex: str | None) -> str | None:
    text = _blob(hit)
    compact = re.sub(r"\s+", "", text)
    if anchor_celex:
        for variant in _celex_variants(anchor_celex):
            if variant in compact or variant in text:
                return "celex"
    if taxonomy.detect_family(text) == label:
        return "family"
    for kw in _label_keywords(label):
        if len(kw) >= 4 and kw in text:
            return "keyword"
    return None


def _cache_hit_matches_label(update: dict[str, Any], label: str, since: str) -> str | None:
    pub = update.get("published_date") or update.get("effective_date") or ""
    if pub and pub < since:
        return None
    if update.get("regulation_family") == label:
        return "family"
    text = _blob(update)
    if taxonomy.detect_family(text) == label:
        return "family"
    anchor = label_regs.EU_LABEL_CELEX.get(label)
    if anchor:
        celex = anchor[0]
        for variant in _celex_variants(celex):
            if variant in re.sub(r"\s+", "", text):
                return "celex"
    for kw in _label_keywords(label):
        if len(kw) >= 4 and kw in text:
            return "keyword"
    return None


def fetch_regulation(
    labels: list[str],
    delivery_countries: list[str],
    *,
    product_id: str = "",
    save: bool = True,
) -> dict[str, Any]:
    """
    Fetch related regulations for compliance labels + markets and persist to backend.

    Tech-lead name: fetchregulation().
    """
    labels_norm = sorted({l.strip() for l in labels if l and l.strip()})
    countries_norm = sorted({c.strip().upper() for c in delivery_countries if c and c.strip()})
    if not labels_norm:
        return {"error": "labels_required", "message": "At least one compliance label is required."}
    if not countries_norm:
        return {"error": "countries_required", "message": "At least one delivery country is required."}

    pid = (product_id or "").strip() or "_catalog"
    if save:
        stored = label_regs.store_product_regulations(pid, labels_norm, countries_norm)
        return {
            "product_id": pid,
            "labels": labels_norm,
            "countries": countries_norm,
            "saved": True,
            "regulations": stored.get("regulations", []),
            "count": len(stored.get("regulations", [])),
        }

    result = label_regs.resolve_labels(labels_norm, countries_norm, product_id=pid or None)
    return {
        "product_id": pid,
        "labels": labels_norm,
        "countries": countries_norm,
        "saved": False,
        **result,
    }


# Tech-lead alias (camelCase)
fetchregulation = fetch_regulation


def check_label(
    label: str,
    since: str | None = None,
    *,
    include_cache: bool = True,
    oj_limit: int = 20,
) -> dict[str, Any]:
    """
    Check whether a compliance label has newly published or amended rules (EU OJ RSS).

    Tech-lead name: check(label).
    """
    label = label.strip()
    if not label:
        return {"error": "label_required", "message": "Compliance label is required (e.g. Battery, REACH)."}

    if since:
        since_date = since[:10]
    else:
        since_date = (date.today() - timedelta(days=DEFAULT_CHECK_DAYS)).isoformat()

    anchor = label_regs.EU_LABEL_CELEX.get(label)
    anchor_celex = anchor[0] if anchor else None
    anchor_title = anchor[1] if anchor else None

    oj_raw = oj_rss.fetch_oj_rss_raw(since_date)
    oj_matches: list[dict[str, Any]] = []
    for hit in oj_raw:
        reason = _oj_hit_matches_label(hit, label, anchor_celex)
        if not reason:
            continue
        record = translate.from_oj_rss(hit)
        oj_matches.append({
            **record,
            "match_reason": reason,
            "oj_series": hit.get("oj_series"),
        })
        if len(oj_matches) >= oj_limit:
            break

    cache_matches: list[dict[str, Any]] = []
    if include_cache:
        cache = load_cache()
        for update in cache.get("updates", []):
            reason = _cache_hit_matches_label(update, label, since_date)
            if not reason:
                continue
            cache_matches.append({
                "update_id": update.get("update_id") or update.get("dedup_key"),
                "source": update.get("source"),
                "title": update.get("title"),
                "reference": update.get("reference"),
                "published_date": update.get("published_date"),
                "change_type": update.get("change_type"),
                "source_url": update.get("source_url"),
                "match_reason": reason,
            })

    has_recent = bool(oj_matches or cache_matches)
    change_types = sorted({m.get("change_type") for m in oj_matches + cache_matches if m.get("change_type")})

    return {
        "label": label,
        "since": since_date,
        "anchor_celex": anchor_celex,
        "anchor_title": anchor_title,
        "has_recent_changes": has_recent,
        "change_types": change_types,
        "oj_count": len(oj_matches),
        "cache_count": len(cache_matches),
        "oj_updates": oj_matches,
        "cache_updates": cache_matches[:oj_limit],
        "feeds": oj_rss.OJ_RSS_FEEDS,
    }


# Tech-lead alias
def check(label: str, since: str | None = None, **kwargs: Any) -> dict[str, Any]:
    return check_label(label, since, **kwargs)
