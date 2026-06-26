"""Cache full regulation text from live APIs — skip re-fetch when already stored."""

from __future__ import annotations

import html as html_lib
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from radar.config import FEED, OPENLEGALDATA_BASE, ensure_dirs, env, load_dotenv

REGTEXT_INDEX = FEED / "regulation_texts.json"
REGTEXT_DIR = FEED / "regulations"

MAX_TEXT_CHARS = 100_000
INLINE_MAX = 8_000
TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; RegulatoryRadar/1.0; +https://github.com/Bobathon2026)"


# Wrong year in CELEX is a common mistake (REACH is 1907/2006 → 32006R1907, not 32007R1907).
CELEX_ALIASES: dict[str, str] = {
    "32007R1907": "32006R1907",
}

CELEX_OJ_URI: dict[str, str] = {
    "32006R1907": "OJ:L:2007:136:FULL",
}


def _normalize_celex(celex: str) -> str:
    celex = celex.replace("CELEX ", "").strip()
    return CELEX_ALIASES.get(celex, celex)


def _is_error_cache(text: str, source: str = "") -> bool:
    if "(fetch error:" in (text or ""):
        return True
    if source == "EUR-Lex" and text and len(text) < 12000 and not _eurlex_text_usable(text):
        return True
    return False


def _eurlex_text_usable(text: str) -> bool:
    if len(text) < 8000:
        return False
    low = text.lower()
    markers = ("article", "regulation", "directive", "annex", "shall", "paragraph")
    marker_hits = sum(m in low for m in markers)
    if len(text) > 80_000 and marker_hits >= 3:
        return True
    if "search results - eur-lex" in low[:600]:
        return False
    if "my eur-lex" in low[:700] and "sign in" in low[:700] and marker_hits < 3:
        return False
    return marker_hits >= 2


def _eurlex_urls(celex: str) -> list[str]:
    """CELEX ALL/TXT, OJ, and ELI URLs."""
    celex = _normalize_celex(celex.replace("CELEX ", "").strip())
    urls: list[str] = []

    urls.append(f"https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:{celex}")

    oj = CELEX_OJ_URI.get(celex)
    if oj:
        urls.append(f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri={oj}")
        urls.append(f"https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri={oj}")

    urls.append(f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}")
    urls.append(f"https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{celex}")

    if len(celex) >= 10 and celex[0] == "3":
        year = celex[1:5]
        kind = celex[5]
        num_full = celex[6:]
        num_trim = num_full.lstrip("0") or num_full
        type_map = {"R": "reg", "L": "dir", "D": "dec"}
        eli_kind = type_map.get(kind)
        if eli_kind:
            urls.append(f"https://eur-lex.europa.eu/eli/{eli_kind}/{year}/{num_trim}/oj")
            if num_trim != num_full:
                urls.append(f"https://eur-lex.europa.eu/eli/{eli_kind}/{year}/{num_full}/oj")

    seen: set[str] = set()
    ordered: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


def make_key(source: str, reference: str) -> str:
    ref = re.sub(r"[^\w\-.]+", "_", (reference or "unknown").strip())[:96]
    src = re.sub(r"[^\w\-.]+", "_", (source or "unknown").strip())
    return f"{src}__{ref}"


def _load_index() -> dict[str, dict]:
    ensure_dirs()
    if not REGTEXT_INDEX.exists():
        return {}
    return json.loads(REGTEXT_INDEX.read_text(encoding="utf-8"))


def _save_index(index: dict[str, dict]) -> None:
    ensure_dirs()
    REGTEXT_DIR.mkdir(exist_ok=True)
    REGTEXT_INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_json_file(filename: str, payload: dict[str, Any]) -> None:
    REGTEXT_DIR.mkdir(exist_ok=True)
    (REGTEXT_DIR / filename).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_json_file(path: str) -> dict[str, Any]:
    full = REGTEXT_DIR / path
    if not full.exists():
        return {}
    try:
        data = json.loads(full.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _read_text_file(path: str) -> str:
    full = REGTEXT_DIR / path
    if not full.exists():
        return ""
    if path.endswith(".json"):
        text = _read_json_file(path).get("text")
        return text if isinstance(text, str) else ""
    return full.read_text(encoding="utf-8")


def html_to_text(raw_html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _http_get(url: str, headers: dict | None = None) -> bytes:
    base = {"User-Agent": USER_AGENT}
    if headers:
        base.update(headers)
    req = urllib.request.Request(url, headers=base, method="GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def get_by_key(key: str) -> dict | None:
    index = _load_index()
    entry = index.get(key)
    if not entry:
        return None
    text = entry.get("text", "")
    if not text and entry.get("file"):
        text = _read_text_file(entry["file"])
    return {**entry, "text": text, "from_cache": True}


def get(source: str, reference: str) -> dict | None:
    return get_by_key(make_key(source, reference))


def _store(key: str, source: str, reference: str, title: str, text: str, url: str = "") -> dict:
    truncated = len(text) > MAX_TEXT_CHARS
    if truncated:
        text = text[:MAX_TEXT_CHARS]

    filename = ""
    file_payload: dict[str, Any] | None = None
    if len(text) > INLINE_MAX:
        filename = f"{key}.json"
        file_payload = {
            "key": key,
            "source": source,
            "reference": reference,
            "title": title,
            "url": url,
            "text": text,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "chars": len(text),
            "truncated": truncated,
        }
        _write_json_file(filename, file_payload)

    record = {
        "key": key,
        "source": source,
        "reference": reference,
        "title": title,
        "url": url,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "chars": len(text),
        "truncated": truncated,
        "file": filename or None,
    }
    index = _load_index()
    index[key] = record
    if not filename:
        index[key]["text"] = text
    _save_index(index)
    return {**record, "text": text, "from_cache": False}


def _fetch_openlegaldata(raw: dict[str, Any]) -> tuple[str, str]:
    law_id = raw.get("id")
    if not law_id:
        raise ValueError("Open Legal Data record missing id")
    load_dotenv()
    headers: dict[str, str] = {"Accept": "application/json"}
    api_key = env("OPENLEGALDATA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Token {api_key}"
    url = f"{OPENLEGALDATA_BASE}/laws/{law_id}/"
    data = json.loads(_http_get(url, headers).decode("utf-8"))
    content = data.get("content") or ""
    text = html_to_text(content) if "<" in content else content
    title = data.get("title") or raw.get("title") or ""
    page_url = f"https://de.openlegaldata.io/laws/{law_id}/"
    if not text.strip():
        text = f"{title} {data.get('book_code', '')} {data.get('section', '')}".strip()
    return text, page_url


def _fetch_eurlex(raw: dict[str, Any], reference: str) -> tuple[str, str]:
    celex = _normalize_celex(raw.get("celex") or reference.replace("CELEX ", "").strip())
    if not celex:
        raise ValueError("EUR-Lex record missing CELEX id")

    last_err: Exception | None = None
    for url in _eurlex_urls(celex):
        try:
            html = _http_get(url).decode("utf-8", errors="replace")
            text = html_to_text(html)
            if _eurlex_text_usable(text):
                return text, url
        except Exception as e:
            last_err = e

    title = raw.get("title") or reference
    if last_err:
        raise last_err
    raise ValueError(f"EUR-Lex returned no usable text for CELEX {celex} ({title})")


def _fetch_bundestag(raw: dict[str, Any]) -> tuple[str, str]:
    title = raw.get("titel", "")
    doc_id = raw.get("id", "")
    parts = [title]
    for field in ("abstract", "beschluss", "sachgebiet"):
        if raw.get(field):
            parts.append(str(raw[field]))
    drucksache = ""
    for d in raw.get("drucksache", []) or []:
        drucksache = d.get("dokumentnummer", drucksache)
        if d.get("titel"):
            parts.append(str(d["titel"]))
    if drucksache:
        parts.append(f"Drucksache {drucksache}")
    url = f"https://dip.bundestag.de/vorgang/{doc_id}" if doc_id else "https://dip.bundestag.de"
    text = "\n\n".join(p for p in parts if p).strip()
    return text or title, url


def _fetch_echa(raw: dict[str, Any], reference: str) -> tuple[str, str]:
    title = raw.get("title") or reference
    summary = raw.get("summary") or f"ECHA substance listing: {reference}"
    url = raw.get("url") or "https://echa.europa.eu/candidate-list-table"
    return f"{title}\n\n{summary}", url


def _fetch_gadi(raw: dict[str, Any], reference: str) -> tuple[str, str]:
    from radar.ingest import gadi

    abbrev = (raw.get("abbreviation") or reference.replace("DE-", "")).strip()
    if not abbrev:
        raise ValueError("GADI record missing abbreviation")
    payload = gadi.fetch_law(abbrev) if not raw.get("payload") else raw["payload"]
    meta = gadi.law_metadata(payload)
    text = gadi.contents_to_text(payload)
    if not text.strip():
        text = meta.get("title") or abbrev
    return text, meta.get("source_url") or gadi.law_json_url(abbrev)


def fetch_from_api(source: str, reference: str, title: str, raw: dict[str, Any] | None) -> tuple[str, str]:
    raw = raw or {}
    if source == "OpenLegalData":
        return _fetch_openlegaldata(raw)
    if source in ("EUR-Lex", "EU Official Journal"):
        return _fetch_eurlex(raw, reference)
    if source == "Bundestag":
        return _fetch_bundestag(raw)
    if source == "ECHA":
        return _fetch_echa(raw, reference)
    if source == "GADI":
        return _fetch_gadi(raw, reference)
    raise ValueError(f"No regulation text fetcher for source: {source}")


def get_or_fetch(
    source: str,
    reference: str,
    title: str,
    raw: dict[str, Any] | None = None,
    *,
    force: bool = False,
) -> dict:
    """Return cached regulation text or fetch from API, save, and return."""
    load_dotenv()
    key = make_key(source, reference)
    if not force:
        cached = get_by_key(key)
        if cached and cached.get("text") and not _is_error_cache(cached["text"], source):
            return cached

    try:
        text, url = fetch_from_api(source, reference, title, raw)
        return _store(key, source, reference, title, text, url)
    except Exception as e:
        fallback = f"{title}\n\nReference: {reference}\nSource: {source}\n(fetch error: {e})"
        # Do not persist failed fetches — keeps cache clean and allows retry after fixes.
        return {
            "key": key,
            "source": source,
            "reference": reference,
            "title": title,
            "url": "",
            "text": fallback,
            "chars": len(fallback),
            "from_cache": False,
            "fetch_failed": True,
        }


def _raw_from_update(update: dict[str, Any]) -> dict[str, Any]:
    """Rebuild minimal API raw payload from a cached update (for on-demand fetch)."""
    raw: dict[str, Any] = {
        "title": update.get("title"),
        "reference": update.get("reference"),
        "summary": update.get("summary"),
    }
    source = update.get("source", "")
    ref = update.get("reference", "")
    if source == "EUR-Lex":
        raw["celex"] = _normalize_celex(ref.replace("CELEX ", "").strip())
    if source == "EU Official Journal":
        raw["celex"] = _normalize_celex(ref.replace("CELEX ", "").strip())
    url = update.get("source_url", "")
    if source == "OpenLegalData" and "/laws/" in url:
        m = re.search(r"/laws/(\d+)/", url)
        if m:
            raw["id"] = int(m.group(1))
    return raw


def attach_to_update(update: dict[str, Any], raw: dict[str, Any] | None = None) -> dict[str, Any]:
    """Enrich a regulatory update with cached or freshly fetched full text."""
    source = update.get("source", "")
    reference = update.get("reference") or update.get("title") or ""
    title = update.get("title") or reference
    payload = raw if raw else _raw_from_update(update)
    record = get_or_fetch(source, reference, title, payload)

    update["regulation_text_key"] = record["key"]
    update["regulation_text_cached"] = bool(record.get("from_cache"))
    update["regulation_text_chars"] = record.get("chars", 0)
    update["regulation_text_preview"] = (record.get("text") or "")[:500]

    knowledge = update.get("mcp_knowledge") or {}
    full_for_embed = (record.get("text") or "")[:8000]
    if full_for_embed:
        knowledge["text_blob"] = f"{title} {reference} {full_for_embed}"
        knowledge["regulation_text_key"] = record["key"]
    update["mcp_knowledge"] = knowledge
    return update


def stats() -> dict[str, int]:
    index = _load_index()
    return {"cached_regulations": len(index), "total_chars": sum(e.get("chars", 0) for e in index.values())}


def list_cached() -> list[dict]:
    index = _load_index()
    return [{**meta, "key": key} for key, meta in index.items()]
