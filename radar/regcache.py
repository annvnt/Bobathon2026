"""Cache full regulation text from live APIs — skip re-fetch when already stored."""

from __future__ import annotations

import html as html_lib
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from radar.config import OPENLEGALDATA_BASE, ensure_dirs, env, load_dotenv

REGTEXT_INDEX = Path(__file__).resolve().parent.parent / "feed" / "regulation_texts.json"
REGTEXT_DIR = Path(__file__).resolve().parent.parent / "feed" / "regulations"

MAX_TEXT_CHARS = 100_000
INLINE_MAX = 8_000
TIMEOUT = 30


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


def _read_text_file(path: str) -> str:
    full = REGTEXT_DIR / path
    if not full.exists():
        return ""
    return full.read_text(encoding="utf-8")


def _write_text_file(filename: str, text: str) -> None:
    REGTEXT_DIR.mkdir(exist_ok=True)
    (REGTEXT_DIR / filename).write_text(text, encoding="utf-8")


def html_to_text(raw_html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _http_get(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "RegulatoryRadar/1.0"}, method="GET")
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
    if len(text) > INLINE_MAX:
        filename = f"{key}.txt"
        _write_text_file(filename, text)

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
    celex = raw.get("celex") or reference.replace("CELEX ", "").strip()
    if not celex:
        raise ValueError("EUR-Lex record missing CELEX id")
    url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
    html = _http_get(url).decode("utf-8", errors="replace")
    text = html_to_text(html)
    if len(text) < 200:
        title = raw.get("title") or reference
        text = f"{title}\n\nCELEX: {celex}\nSource: {url}"
    return text, url


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


def fetch_from_api(source: str, reference: str, title: str, raw: dict[str, Any] | None) -> tuple[str, str]:
    raw = raw or {}
    if source == "OpenLegalData":
        return _fetch_openlegaldata(raw)
    if source == "EUR-Lex":
        return _fetch_eurlex(raw, reference)
    if source == "Bundestag":
        return _fetch_bundestag(raw)
    if source == "ECHA":
        return _fetch_echa(raw, reference)
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
        if cached and cached.get("text"):
            return cached

    try:
        text, url = fetch_from_api(source, reference, title, raw)
        return _store(key, source, reference, title, text, url)
    except Exception as e:
        fallback = f"{title}\n\nReference: {reference}\nSource: {source}\n(fetch error: {e})"
        return _store(key, source, reference, title, fallback, "")


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
        raw["celex"] = ref.replace("CELEX ", "").strip()
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
