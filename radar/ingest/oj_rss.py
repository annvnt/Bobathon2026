"""EU Official Journal — EUR-Lex predefined RSS feeds (daily L/C series)."""

from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

from radar.config import env, load_dotenv

TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; RegulatoryRadar/1.0)"

# EUR-Lex predefined RSS — https://eur-lex.europa.eu/content/help/search/predefined-rss.html
OJ_RSS_FEEDS: dict[str, dict[str, Any]] = {
    "L": {
        "rss_id": 222,
        "name": "Official Journal L (Legislation)",
        "description": "Newly published acts in the OJ L series",
    },
    "C": {
        "rss_id": 221,
        "name": "Official Journal C (Information & Notices)",
        "description": "Notices, corrigenda, preparatory acts in the OJ C series",
    },
}

CELEX_TITLE = re.compile(r"^CELEX:([^:\s]+)(?::\s*(.+))?", re.I)


def _feed_url(rss_id: int) -> str:
    lang = env("EURLEX_RSS_LANG", "EN")
    return f"https://eur-lex.europa.eu/{lang}/display-feed.rss?rssId={rss_id}"


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _parse_pub_date(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None


def _infer_change_type(celex: str, title: str, description: str) -> str:
    blob = f"{celex} {title} {description}".lower()
    if "corrigendum" in blob or re.search(r"R\(\d+\)", celex):
        return "corrigendum"
    if "amending" in blob or "amendment" in blob:
        return "amendment"
    return "new"


def _normalize_link(link: str) -> str:
    return link.replace("/./", "/").replace("AUTO", "EN/TXT")


def parse_rss_item(item: ET.Element, *, series: str) -> dict[str, Any] | None:
    title_raw = _text(item.find("title"))
    m = CELEX_TITLE.match(title_raw)
    if not m:
        return None
    celex = m.group(1).strip()
    doc_title = (m.group(2) or title_raw).strip()
    description = _text(item.find("description"))
    link = _normalize_link(_text(item.find("link")))
    pub = _parse_pub_date(_text(item.find("pubDate")))
    creator = _text(item.find("{http://purl.org/dc/elements/1.1/}creator"))
    change_type = _infer_change_type(celex, doc_title, description)
    summary = description or doc_title
    if creator:
        summary = f"{summary} ({creator})".strip()
    return {
        "celex": celex,
        "title": doc_title,
        "reference": celex,
        "summary": summary,
        "url": link or f"https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:{celex}",
        "published_date": pub.date().isoformat() if pub else None,
        "pub_datetime": pub.isoformat() if pub else None,
        "oj_series": series,
        "change_type": change_type,
        "creator": creator,
    }


def fetch_feed(series: str, last_fetched: str) -> list[dict[str, Any]]:
    """Fetch one OJ RSS series and return items on or after last_fetched (YYYY-MM-DD)."""
    load_dotenv()
    meta = OJ_RSS_FEEDS[series]
    url = _feed_url(meta["rss_id"])
    try:
        raw = _http_get(url)
    except Exception as e:
        print(f"EU-OJ: RSS {series} fetch error — {e}")
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"EU-OJ: RSS {series} parse error — {e}")
        return []

    cutoff = datetime.strptime(last_fetched[:10], "%Y-%m-%d").date()
    hits: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        parsed = parse_rss_item(item, series=series)
        if not parsed:
            continue
        pub = parsed.get("published_date")
        if pub and pub < str(cutoff):
            continue
        hits.append(parsed)
    return hits


def fetch_oj_rss_raw(last_fetched: str) -> list[dict[str, Any]]:
    """Fetch OJ L + C RSS items since last_fetched."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for series in OJ_RSS_FEEDS:
        for hit in fetch_feed(series, last_fetched):
            celex = hit["celex"]
            if celex in seen:
                continue
            seen.add(celex)
            out.append(hit)
    out.sort(key=lambda h: h.get("published_date") or "", reverse=True)
    return out
