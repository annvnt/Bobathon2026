"""Live ingestion from EUR-Lex, Bundestag DIP, Open Legal Data, and local ECHA lists."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Any, Callable

from radar import sources, translate
from radar.config import (
    CACHE_FILE,
    DIP_BASE,
    ECHA_DIR,
    EURLEX_WS_URL,
    OPENLEGALDATA_BASE,
    STATE_FILE,
    ensure_dirs,
    env,
    load_dotenv,
)

# EUR-Lex SOAP namespaces
NS = {
    "soap": "http://schemas.xmlsoap.org/soap/envelope/",
    "sear": "http://eur-lex.europa.eu/search",
}

FALLBACK_CELEX = [
    ("32023R1542", "EU Battery Regulation (EU) 2023/1542"),
    ("32011L0065", "RoHS Directive 2011/65/EU"),
    ("32007R1907", "REACH Regulation (EC) 1907/2006"),
]

TIMEOUT = 30
MAX_RETRIES = 3


def _read_json(path) -> Any:
    if not path.exists():
        return {} if path.name == "state.json" else {"updates": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_cache() -> dict:
    data = _read_json(CACHE_FILE)
    if isinstance(data, list):
        return {"updates": data}
    return data


def save_cache(cache: dict) -> None:
    _write_json(CACHE_FILE, cache)


def load_state() -> dict:
    return _read_json(STATE_FILE)


def save_state(state: dict) -> None:
    state["last_run"] = datetime.utcnow().isoformat() + "Z"
    _write_json(STATE_FILE, state)


def merge_updates(cache: dict, new_records: list[dict]) -> int:
    """Append deduplicated updates; replace on correction/amendment."""
    by_key = {u.get("dedup_key"): u for u in cache.get("updates", []) if u.get("dedup_key")}
    added = 0
    for rec in new_records:
        key = rec.get("dedup_key")
        if not key:
            continue
        if rec.get("change_type") in ("correction", "amendment") or key not in by_key:
            if key not in by_key:
                added += 1
            by_key[key] = rec
    cache["updates"] = list(by_key.values())
    return added


def _http_get(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
                continue
            raise
    return b""


def _http_post(url: str, body: bytes, headers: dict) -> bytes:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < MAX_RETRIES - 1:
                time.sleep(5)
                continue
            raise
    return b""


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _xml_text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def fetch_eurlex_raw(last_fetched: str) -> list[dict]:
    """EUR-Lex SOAP raw hits — requires EURLEX_USER / EURLEX_PASSWORD."""
    user, password = env("EURLEX_USER"), env("EURLEX_PASSWORD")
    if not user or not password:
        raise ValueError("EURLEX_USER and EURLEX_PASSWORD required for live EUR-Lex API")

    query = (
        f'DC_TYPE = REGULATION AND (SUBJECT = REACH OR SUBJECT = RoHS OR TI ~ battery) '
        f'AND PD >= {last_fetched.replace("-", "/")}'
    )
    hits: list[dict] = []
    page = 1
    page_size = 50
    total = None

    while total is None or (page - 1) * page_size < total:
        envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:sear="http://eur-lex.europa.eu/search">
  <soap:Header/>
  <soap:Body>
    <sear:searchRequest>
      <sear:expertQuery>{query}</sear:expertQuery>
      <sear:page>{page}</sear:page>
      <sear:pageSize>{page_size}</sear:pageSize>
      <sear:searchLanguage>en</sear:searchLanguage>
    </sear:searchRequest>
  </soap:Body>
</soap:Envelope>"""
        cred = base64.b64encode(f"{user}:{password}".encode()).decode()
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "search",
            "Authorization": f"Basic {cred}",
        }
        raw = _http_post(EURLEX_WS_URL, envelope.encode("utf-8"), headers)
        page_hits, total_hits = _parse_eurlex_response(raw)
        total = total_hits
        hits.extend(page_hits)
        if not page_hits:
            break
        page += 1

    return hits


def eurlex_fallback_raw() -> list[dict]:
    """Known CELEX anchors when live SOAP unavailable."""
    out = []
    for celex, title in FALLBACK_CELEX:
        year = celex[1:5]
        kind = celex[5]
        num = celex[6:]
        if kind == "R":
            url = f"https://eur-lex.europa.eu/eli/reg/{year}/{num}/oj"
        else:
            url = f"https://eur-lex.europa.eu/eli/dir/{year}/{num}/oj"
        out.append({
            "celex": celex,
            "title": title,
            "reference": celex,
            "applicable_date": "2023-08-17" if "1542" in celex else "2011-07-21",
            "url": url,
        })
    return out


def fetch_eurlex(last_fetched: str) -> list[dict]:
    user, password = env("EURLEX_USER"), env("EURLEX_PASSWORD")
    if not user or not password:
        print("EUR-Lex: skipping (EURLEX_USER / EURLEX_PASSWORD not set)")
        return [translate.from_eurlex(h) for h in eurlex_fallback_raw()]
    try:
        return [translate.from_eurlex(h) for h in fetch_eurlex_raw(last_fetched)]
    except Exception as e:
        print(f"EUR-Lex SOAP error: {e}")
        return [translate.from_eurlex(h) for h in eurlex_fallback_raw()]


def _parse_eurlex_response(raw: bytes) -> tuple[list[dict], int]:
    root = ET.fromstring(raw)
    total = 0
    for el in root.iter():
        if _local(el.tag) == "totalHits":
            total = int(_xml_text(el) or "0")
            break

    hits: list[dict] = []
    for hit in root.iter():
        if _local(hit.tag) != "result":
            continue
        celex = title = ref = app_date = ""
        for child in hit.iter():
            tag = _local(child.tag)
            if tag == "VALUE" and not celex and _xml_text(child).startswith("3"):
                celex = _xml_text(child)
            if tag == "REFERENCE":
                ref = _xml_text(child)
            if tag in ("TITLE", "title"):
                title = _xml_text(child) or title
            if tag == "APPLICABLE_DATE":
                app_date = _xml_text(child)
        if celex or title:
            hits.append({
                "celex": celex or ref,
                "title": title or ref,
                "reference": ref or celex,
                "applicable_date": app_date,
                "url": f"https://eur-lex.europa.eu/eli/reg/{celex[1:5]}R{celex[5:]}/oj" if celex and "R" in celex[4:6] else None,
            })
    return hits, total


def _eurlex_fallback() -> list[dict]:
    return [translate.from_eurlex(h) for h in eurlex_fallback_raw()]


def fetch_bundestag_raw(last_fetched: str) -> list[dict]:
    """Bundestag DIP raw documents — requires BUNDESTAG_DIP_KEY."""
    apikey = env("BUNDESTAG_DIP_KEY")
    if not apikey:
        raise ValueError("BUNDESTAG_DIP_KEY required for live Bundestag DIP API")

    docs: list[dict] = []
    for term in sources.DIP_SEARCH_TERMS:
        cursor = "*"
        while cursor:
            params = {
                "apikey": apikey,
                "f.vorgangstyp": "Gesetzgebung",
                "f.wahlperiode": "20",
                "f.datum.start": last_fetched,
                "term": term,
                "format": "json",
                "rows": "50",
                "cursor": cursor,
            }
            url = f"{DIP_BASE}/vorgang?{urllib.parse.urlencode(params)}"
            data = json.loads(_http_get(url).decode("utf-8"))
            docs.extend(data.get("documents", []))
            cursor = data.get("cursorMark") or data.get("cursor")
            if cursor == "*" or not data.get("documents"):
                break
    return docs


def fetch_bundestag(last_fetched: str) -> list[dict]:
    apikey = env("BUNDESTAG_DIP_KEY")
    if not apikey:
        print("Bundestag DIP: skipping (BUNDESTAG_DIP_KEY not set)")
        return []
    try:
        return [translate.from_dip(d) for d in fetch_bundestag_raw(last_fetched)]
    except Exception as e:
        print(f"Bundestag DIP error: {e}")
        return []


def fetch_openlegaldata_raw(last_fetched: str) -> list[dict]:
    """Open Legal Data law books + norms — optional OPENLEGALDATA_API_KEY."""
    api_key = env("OPENLEGALDATA_API_KEY")
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Token {api_key}"

    seen_ids: set[int] = set()
    items: list[dict] = []

    def _fetch_page(url: str) -> dict:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))

    for term in sources.OLDP_SEARCH_TERMS:
        offset = 0
        pages = 0
        while pages < 3:
            params = urllib.parse.urlencode({
                "search": term,
                "limit": "25",
                "offset": str(offset),
                "ordering": "-updated_date",
            })
            url = f"{OPENLEGALDATA_BASE}/laws/?{params}"
            try:
                data = _fetch_page(url)
            except Exception as e:
                print(f"OpenLegalData error ({term}): {e}")
                break
            for item in data.get("results", []):
                if not isinstance(item, dict):
                    continue
                item_id = item.get("id")
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                items.append(item)
            if not data.get("next"):
                break
            offset += 25
            pages += 1

    return items


def fetch_openlegaldata(last_fetched: str) -> list[dict]:
    try:
        return [translate.from_openlegaldata(i) for i in fetch_openlegaldata_raw(last_fetched)]
    except Exception as e:
        print(f"OpenLegalData error: {e}")
        return []


def fetch_echa(last_fetched: str) -> list[dict]:
    """Read ECHA chemical list XLSX files from ECHA/ (candidate, restriction, authorisation)."""
    from radar import echa as echa_mod

    entries = echa_mod.load_entries()
    if not entries:
        st = echa_mod.stats()
        if not st.get("files"):
            print("ECHA: no XLSX files in ECHA/ directory")
        else:
            print(f"ECHA: 0 portfolio-relevant substances (watching: {', '.join(st['portfolio_substances'])})")
        return []

    records = [translate.from_echa(entry) for entry in entries]
    print(f"ECHA: loaded {len(records)} substance entries from {len(echa_mod.stats()['files'])} files")
    return records


CONNECTORS: dict[str, Callable[[str], list[dict]]] = {
    "EUR-Lex": fetch_eurlex,
    "Bundestag": fetch_bundestag,
    "OpenLegalData": fetch_openlegaldata,
    "ECHA": fetch_echa,
}


def ingest(sources_filter: tuple[str, ...] | None = None) -> int:
    """Delegate to MCP API-key-driven fetch."""
    from radar import mcp
    result = mcp.fetch_from_apis(sources_filter)
    return result.get("ingested_new", 0)
