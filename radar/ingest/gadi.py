"""Fetch and parse German federal laws from GADI (gesetze-im-internet JSON mirror)."""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from radar.config import GADI_BASE
from radar.ingest.regcache import html_to_text

TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; RegulatoryRadar/1.0; +https://github.com/Bobathon2026)"

# GADI slugs are sometimes wrong on gesetze-im-internet.de — use known-good URLs.
DE_OFFICIAL_URLS: dict[str, str] = {
    "ElektroG": "https://www.gesetze-im-internet.de/elektrog_2015/",
    "ChemG": "https://www.gesetze-im-internet.de/chemg/",
    "ProdSG": "https://www.gesetze-im-internet.de/prodsg_2021/",
    "1_ProdSV": "https://www.gesetze-im-internet.de/prodsg2011v_1/index.html",
    "2_ProdSV": "https://www.gesetze-im-internet.de/gpsgv_2/",
    "9_ProdSV": "https://www.gesetze-im-internet.de/gsgv_9/",
}


def law_json_url(abbreviation: str) -> str:
    return f"{GADI_BASE}/laws/{abbreviation}.json"


def fetch_law(abbreviation: str) -> dict[str, Any]:
    """Download one law JSON document from gadi.netlify.app."""
    url = law_json_url(abbreviation)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"GADI returned non-object JSON for {abbreviation}")
    return payload


def _law_root(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    return payload


def law_metadata(payload: dict[str, Any]) -> dict[str, str]:
    law = _law_root(payload)
    abbrev = (law.get("abbreviation") or "").strip()
    slug = (law.get("slug") or abbrev.lower()).strip()
    title = (law.get("titleLong") or law.get("titleShort") or abbrev).strip()
    source_url = official_source_url(abbrev) or (
        f"https://www.gesetze-im-internet.de/{slug}/" if slug else GADI_BASE
    )
    return {
        "abbreviation": abbrev,
        "slug": slug,
        "title": title,
        "source_url": source_url,
        "gadi_url": law_json_url(abbrev) if abbrev else GADI_BASE,
    }


# GADI slugs are sometimes wrong — use verified gesetze-im-internet.de URLs
OFFICIAL_LAW_URLS: dict[str, str] = {
    "BattDG": "https://www.gesetze-im-internet.de/battdg/",
    "VerpackG": "https://www.gesetze-im-internet.de/verpackg/",
    "ElektroG": "https://www.gesetze-im-internet.de/elektrog_2015/",
    "ChemG": "https://www.gesetze-im-internet.de/chemg/",
    "ProdSG": "https://www.gesetze-im-internet.de/prodsg_2021/",
    "1_ProdSV": "https://www.gesetze-im-internet.de/prodsg2011v_1/index.html",
    "2_ProdSV": "https://www.gesetze-im-internet.de/gpsgv_2/index.html",
    "9_ProdSV": "https://www.gesetze-im-internet.de/gsgv_9/",
    "EMVG": "https://www.gesetze-im-internet.de/emvg/",
    "FuAG": "https://www.gesetze-im-internet.de/fuag/",
    "EnVKG": "https://www.gesetze-im-internet.de/envkg/",
    "MPDG": "https://www.gesetze-im-internet.de/mpdg/",
}


def official_source_url(abbreviation: str) -> str:
    return OFFICIAL_LAW_URLS.get(abbreviation.strip(), "")


def _body_to_text(body: str) -> str:
    if not body:
        return ""
    if "<" in body:
        return html_to_text(body)
    return re.sub(r"\s+", " ", body).strip()


def contents_to_text(payload: dict[str, Any], *, max_chars: int | None = None) -> str:
    """Flatten GADI `contents[]` articles into searchable plain text."""
    law = _law_root(payload)
    parts: list[str] = []
    title = (law.get("titleLong") or law.get("titleShort") or law.get("abbreviation") or "").strip()
    if title:
        parts.append(title)

    for item in law.get("contents") or []:
        if not isinstance(item, dict):
            continue
        heading = (item.get("name") or item.get("title") or "").strip()
        body = _body_to_text(item.get("body") or "")
        if heading:
            parts.append(heading)
        if body:
            parts.append(body)

    text = "\n\n".join(p for p in parts if p).strip()
    if max_chars and len(text) > max_chars:
        return text[:max_chars]
    return text
