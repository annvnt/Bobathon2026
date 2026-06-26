"""
MCP — map AI product labels + delivery countries to stored regulations.

Each stored record (JSON):
  label              — data source (EUR-Lex, GADI, …)
  category           — compliance subject (Battery, REACH, RoHS, …)
  country            — jurisdiction (EU, DE, …)
  countries_affected — markets the rule covers (EU → all member states)
  text               — full regulation text (in per-item JSON file when saved)
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from radar.compliance.jurisdictions import countries_affected, expand_jurisdictions
from radar.config import LABEL_REGULATION_ITEMS_DIR, REGULATION_LIBRARY_FILE, ensure_dirs
from radar.ingest import gadi, regcache, translate

# compliance_stream → regulation code (CELEX / GADI abbrev) — single lookup table
# de_eu_transposition=True → skip DE (national ordinance transposing the EU act; EU CELEX is enough)
STREAM_REG_CODES: dict[str, dict[str, str | bool]] = {
    "Battery": {"eu_celex": "32023R1542", "de_code": "BattDG", "eu_title": "EU Battery Regulation (EU) 2023/1542", "de_eu_transposition": False},
    "RoHS": {"eu_celex": "32011L0065", "de_code": "ElektroG", "eu_title": "RoHS Directive 2011/65/EU", "de_eu_transposition": True},
    "REACH": {"eu_celex": "32006R1907", "de_code": "ChemG", "eu_title": "REACH Regulation (EC) 1907/2006", "de_eu_transposition": True},
    "WEEE": {"eu_celex": "32012L0019", "de_code": "ElektroG", "eu_title": "WEEE Directive 2012/19/EU", "de_eu_transposition": True},
    "GPSR": {"eu_celex": "32023R0988", "de_code": "ProdSG", "eu_title": "GPSR Regulation (EU) 2023/988", "de_eu_transposition": True},
    "RED": {"eu_celex": "32014L0053", "de_code": "FuAG", "eu_title": "RED Directive 2014/53/EU", "de_eu_transposition": True},
    "PPWR": {"eu_celex": "32025R0040", "de_code": "VerpackG", "eu_title": "PPWR Regulation (EU) 2025/40", "de_eu_transposition": False},
    "EMC": {"eu_celex": "32014L0030", "de_code": "EMVG", "eu_title": "EMC Directive 2014/30/EU", "de_eu_transposition": True},
    "LVD": {"eu_celex": "32014L0035", "de_code": "1_ProdSV", "eu_title": "LVD Directive 2014/35/EU", "de_eu_transposition": True},
    "EnergyLabel": {"eu_celex": "32017R1369", "de_code": "EnVKG", "eu_title": "Energy Labelling Framework Regulation (EU) 2017/1369", "de_eu_transposition": True},
    "ESPR": {"eu_celex": "32024R1781", "de_code": "EnVKG", "eu_title": "ESPR Ecodesign Regulation (EU) 2024/1781", "de_eu_transposition": True},
    "MDR": {"eu_celex": "32017R0745", "de_code": "MPDG", "eu_title": "Medical Devices Regulation (EU) 2017/745", "de_eu_transposition": True},
    "ToySafety": {"eu_celex": "32009L0048", "de_code": "2_ProdSV", "eu_title": "Toy Safety Directive 2009/48/EC", "de_eu_transposition": True},
    "POPs": {"eu_celex": "32019R1021", "de_code": "ChemG", "eu_title": "POPs Regulation (EU) 2019/1021", "de_eu_transposition": True},
    "Machinery": {"eu_celex": "32006L0042", "de_code": "9_ProdSV", "eu_title": "Machinery Directive 2006/42/EC", "de_eu_transposition": True},
}

EU_LABEL_CELEX: dict[str, tuple[str, str]] = {
    k: (str(v["eu_celex"]), str(v["eu_title"])) for k, v in STREAM_REG_CODES.items()
}
DE_LABEL_LAWS: dict[str, list[str]] = {
    k: [str(v["de_code"])] for k, v in STREAM_REG_CODES.items() if not v.get("de_eu_transposition")
}
CELEX_TO_STREAM: dict[str, str] = {str(v["eu_celex"]): k for k, v in STREAM_REG_CODES.items()}
DE_CODE_TO_STREAM: dict[str, str] = {str(v["de_code"]): k for k, v in STREAM_REG_CODES.items()}

PORTFOLIO_COMPLIANCE_STREAMS: tuple[str, ...] = tuple(STREAM_REG_CODES.keys())

# Fallback when GADI fetch fails — keyed by de_code (GADI abbrev)
DE_CODE_ANCHORS: dict[str, dict[str, str]] = {
    "BattDG": {"title": "BattDG — Batterierecht-Durchführungsgesetz", "source_url": "https://www.gesetze-im-internet.de/battdg/", "summary": "German battery act (EU 2023/1542)."},
    "ElektroG": {"title": "ElektroG — Elektro- und Elektronikgerätegesetz", "source_url": "https://www.gesetze-im-internet.de/elektrog_2015/", "summary": "German WEEE / RoHS market-access law."},
    "ChemG": {"title": "ChemG — Chemikaliengesetz", "source_url": "https://www.gesetze-im-internet.de/chemg_2017/", "summary": "German chemicals act (REACH / POPs enforcement)."},
    "ProdSG": {"title": "ProdSG — Produktsicherheitsgesetz", "source_url": "https://www.gesetze-im-internet.de/prodsg/", "summary": "German general product safety act."},
    "VerpackG": {"title": "VerpackG — Verpackungsgesetz", "source_url": "https://www.gesetze-im-internet.de/verpackg/", "summary": "German packaging / EPR law."},
}

# Legacy alias for any code still using stream-keyed anchors
DE_LABEL_ANCHORS: dict[str, list[dict[str, str]]] = {
    stream: [{
        "title": DE_CODE_ANCHORS[codes["de_code"]]["title"],
        "reference": codes["de_code"],
        "abbreviation": codes["de_code"],
        "source_url": DE_CODE_ANCHORS[codes["de_code"]]["source_url"],
        "summary": DE_CODE_ANCHORS[codes["de_code"]]["summary"],
    }]
    for stream, codes in STREAM_REG_CODES.items()
    if codes["de_code"] in DE_CODE_ANCHORS and not codes.get("de_eu_transposition")
}


def should_fetch_de(stream: str) -> bool:
    """False when DE law is only the national transposition of the mapped EU act."""
    codes = STREAM_REG_CODES.get(stream.strip())
    if not codes:
        return True
    return not bool(codes.get("de_eu_transposition"))


def is_de_transposition_record(record: dict[str, Any]) -> bool:
    if (record.get("country") or "").upper() != "DE":
        return False
    return not should_fetch_de(str(record.get("category") or ""))


def _filter_regulations(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in records if not is_de_transposition_record(r)]


def is_celex(code: str) -> bool:
    c = code.strip().upper().replace("CELEX:", "").replace(" ", "")
    return bool(re.match(r"^3\d{4}[RLD]", c))


def normalize_celex(code: str) -> str:
    return code.strip().upper().replace("CELEX:", "").replace(" ", "")


def codes_for_stream(stream: str) -> dict[str, str] | None:
    return STREAM_REG_CODES.get(stream.strip())


def fetch_by_code(code: str, *, stream: str = "") -> dict[str, Any] | None:
    """Fetch one regulation by CELEX (e.g. 32023R1542) or GADI abbrev (e.g. BattDG)."""
    code = code.strip()
    if not code:
        return None
    if is_celex(code):
        celex = normalize_celex(code)
        category = stream or CELEX_TO_STREAM.get(celex, celex)
        title = EU_LABEL_CELEX.get(category, (celex, celex))[1]
        return _fetch_eu_by_celex(celex, category, title)
    category = stream or DE_CODE_TO_STREAM.get(code, code)
    rec = _fetch_gadi_by_code(code, category)
    if rec:
        return rec
    return _de_anchor_by_code(code, category)


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Map legacy fields (source / label) to label + category."""
    out = dict(record)
    if "category" not in out and "label" in out and "source" in out:
        out["category"] = out["label"]
        out["label"] = out.pop("source")
    elif "category" not in out and "source" in out:
        out["category"] = out.get("label", "")
        out["label"] = out.pop("source")
    elif "category" not in out and "label" in out:
        out["category"] = out["label"]
    return out


def _regulation_key(record: dict[str, Any]) -> tuple[Any, ...]:
    rec = _normalize_record(record)
    return (rec.get("category"), rec.get("country"), rec.get("reference"))


def _dedupe_regulations(regulations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    merged: list[dict[str, Any]] = []
    for record in regulations:
        key = _regulation_key(record)
        if key in seen:
            continue
        seen.add(key)
        merged.append(record)
    return merged


def _item_filename(record: dict[str, Any]) -> str:
    rec = _normalize_record(record)
    category = re.sub(r"[^\w\-.]+", "_", (rec.get("category") or "unknown").strip())[:48]
    country = re.sub(r"[^\w\-.]+", "_", (rec.get("country") or "XX").strip())[:8]
    reference = re.sub(r"[^\w\-.]+", "_", (rec.get("reference") or "ref").strip())[:64]
    return f"{category}__{country}__{reference}.json"


def _item_path(filename: str) -> Path:
    return LABEL_REGULATION_ITEMS_DIR / filename


def _write_item(record: dict[str, Any]) -> str:
    ensure_dirs()
    LABEL_REGULATION_ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    rec = _normalize_record(record)
    filename = _item_filename(rec)
    payload = {k: v for k, v in rec.items() if k != "file"}
    _item_path(filename).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return filename


def _read_item(filename: str) -> dict[str, Any]:
    path = _item_path(filename)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _normalize_record(data) if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _index_entry(record: dict[str, Any], filename: str) -> dict[str, Any]:
    rec = _normalize_record(record)
    return {
        "label": rec.get("label"),
        "category": rec.get("category"),
        "country": rec.get("country"),
        "countries_affected": rec.get("countries_affected", []),
        "title": rec.get("title"),
        "reference": rec.get("reference"),
        "source_url": rec.get("source_url"),
        "regulation_text_key": rec.get("regulation_text_key"),
        "stored_at": rec.get("stored_at"),
        "file": filename,
    }


def _hydrate_entry(entry: dict[str, Any]) -> dict[str, Any]:
    rec = _normalize_record(entry)
    filename = rec.get("file")
    if filename:
        item = _read_item(filename)
        if item:
            merged = {**item, **{k: v for k, v in rec.items() if k != "text" and v is not None}}
            return merged
    return rec


def _load_library() -> dict[str, Any]:
    ensure_dirs()
    if not REGULATION_LIBRARY_FILE.exists():
        return {"regulations": []}
    raw = json.loads(REGULATION_LIBRARY_FILE.read_text(encoding="utf-8"))
    if "regulations" in raw and isinstance(raw["regulations"], list):
        entries = [_normalize_record(e) for e in raw["regulations"] if isinstance(e, dict)]
        return {"regulations": _dedupe_regulations(entries)}
    if "products" in raw:
        flat: list[dict[str, Any]] = []
        for entry in raw["products"].values():
            if isinstance(entry, dict):
                flat.extend(entry.get("regulations", []))
            elif isinstance(entry, list):
                flat.extend(entry)
        return {"regulations": _dedupe_regulations([_normalize_record(e) for e in flat])}
    return {"regulations": []}


def _save_library(data: dict[str, Any]) -> None:
    ensure_dirs()
    LABEL_REGULATION_ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    regs = data.get("regulations", [])
    if not isinstance(regs, list):
        regs = []
    index: list[dict[str, Any]] = []
    for record in _dedupe_regulations(regs):
        rec = _normalize_record(record)
        filename = rec.get("file") or _write_item(rec)
        if not _item_path(filename).exists():
            filename = _write_item(rec)
        index.append(_index_entry(rec, filename))
    REGULATION_LIBRARY_FILE.write_text(
        json.dumps({"regulations": index}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _fetch_eu_by_celex(celex: str, category: str, title: str) -> dict[str, Any]:
    source_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
    raw = {"celex": celex, "title": title, "reference": celex}
    update = translate.from_eurlex(raw)
    record = regcache.get_or_fetch("EUR-Lex", celex, title, raw)
    text = record.get("text") or ""
    fetch_failed = bool(record.get("fetch_failed")) or len(text) < 80
    if fetch_failed:
        text = (
            f"{title}\n\n"
            f"CELEX: {celex}\n\n"
            f"Official source: {source_url}\n\n"
            "Full consolidated text is on EUR-Lex. Use Open source to read the act in the browser."
        )
    return {
        "label": "EUR-Lex",
        "category": category,
        "country": "EU",
        "countries_affected": countries_affected("EU"),
        "text": text,
        "title": title,
        "reference": celex,
        "source_url": record.get("url") or update.get("source_url") or source_url,
        "regulation_text_key": None if fetch_failed else record.get("key"),
        "stored_at": datetime.utcnow().isoformat() + "Z",
    }


def _fetch_eu_regulation(category: str) -> dict[str, Any] | None:
    codes = codes_for_stream(category)
    if not codes:
        return None
    return fetch_by_code(codes["eu_celex"], stream=category)


def _fetch_gadi_by_code(abbrev: str, category: str) -> dict[str, Any] | None:
    """Fetch German law by GADI code (BattDG, ChemG, …). Reference = code."""
    try:
        payload = gadi.fetch_law(abbrev)
    except Exception:
        return None
    meta = gadi.law_metadata(payload)
    title = meta.get("title") or abbrev
    cached = regcache.get_or_fetch(
        "GADI",
        abbrev,
        title,
        {"abbreviation": abbrev, "payload": payload},
    )
    if cached.get("fetch_failed"):
        return None
    text = cached.get("text") or ""
    if len(text) < 80:
        return None
    return {
        "label": "GADI",
        "category": category,
        "country": "DE",
        "countries_affected": countries_affected("DE"),
        "text": text,
        "title": title,
        "reference": abbrev,
        "source_url": meta.get("source_url") or gadi.official_source_url(abbrev) or cached.get("url", ""),
        "gadi_url": gadi.law_json_url(abbrev),
        "regulation_text_key": cached.get("key"),
        "stored_at": datetime.utcnow().isoformat() + "Z",
    }


def _fetch_gadi_law(category: str, abbreviation: str) -> dict[str, Any] | None:
    return _fetch_gadi_by_code(abbreviation, category)


def _de_anchor_by_code(abbrev: str, category: str) -> dict[str, Any] | None:
    anchor = DE_CODE_ANCHORS.get(abbrev)
    if not anchor:
        return None
    text = (
        f"{anchor['title']}\n\n"
        f"{anchor['summary']}\n\n"
        f"Official source: {anchor['source_url']}\n"
        f"(GADI: {gadi.law_json_url(abbrev)})"
    )
    return {
        "label": "Germany-Federal",
        "category": category,
        "country": "DE",
        "countries_affected": countries_affected("DE"),
        "text": text,
        "title": anchor["title"],
        "reference": abbrev,
        "source_url": anchor["source_url"],
        "regulation_text_key": None,
        "stored_at": datetime.utcnow().isoformat() + "Z",
    }


def _de_anchor_records(category: str) -> list[dict[str, Any]]:
    codes = codes_for_stream(category)
    if not codes:
        return []
    rec = _de_anchor_by_code(codes["de_code"], category)
    return [rec] if rec else []


def _fetch_de_regulation(category: str) -> list[dict[str, Any]]:
    codes = codes_for_stream(category)
    if not codes:
        return []
    rec = fetch_by_code(codes["de_code"], stream=category)
    return [rec] if rec else _de_anchor_records(category)


def resolve_labels(
    labels: list[str],
    delivery_countries: list[str],
    *,
    product_id: str | None = None,
) -> dict[str, Any]:
    """
    Find regulations for each AI label × jurisdiction (EU + national).

    Does not persist — use store_product_regulations() to save JSON.
    """
    labels_norm = sorted({l.strip() for l in labels if l and l.strip()})
    jurisdictions = expand_jurisdictions(delivery_countries)
    records: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    for label in labels_norm:
        # Direct code lookup: CELEX or GADI abbrev passed as label
        if is_celex(label) or label in DE_CODE_TO_STREAM:
            rec = fetch_by_code(label)
            if rec:
                records.append(rec)
            else:
                missing.append({"label": label, "country": "?", "reason": "code_not_found"})
            continue

        codes = codes_for_stream(label)
        if not codes:
            missing.append({"label": label, "country": "?", "reason": "unknown_stream"})
            continue

        if "EU" in jurisdictions:
            eu_rec = fetch_by_code(codes["eu_celex"], stream=label)
            if eu_rec:
                records.append(eu_rec)
            else:
                missing.append({"label": label, "country": "EU", "reason": "no_eu_anchor"})

        if "DE" in jurisdictions and should_fetch_de(label):
            de_rec = fetch_by_code(str(codes["de_code"]), stream=label)
            if de_rec:
                records.append(de_rec)
            else:
                missing.append({"label": label, "country": "DE", "reason": "no_de_match"})

    records = _filter_regulations(records)
    return {
        "product_id": product_id,
        "labels": labels_norm,
        "delivery_countries": delivery_countries,
        "jurisdictions": jurisdictions,
        "regulations": records,
        "missing": missing,
        "count": len(records),
    }


def store_product_regulations(
    product_id: str,
    labels: list[str],
    delivery_countries: list[str],
) -> dict[str, Any]:
    """Resolve and persist regulations to feed/label_regulations.json + item JSON files."""
    result = resolve_labels(labels, delivery_countries, product_id=product_id)
    lib = _load_library()
    existing = [_hydrate_entry(e) for e in lib.get("regulations", [])]
    lib["regulations"] = _dedupe_regulations(existing + result["regulations"])
    _save_library(lib)
    return {"regulations": result["regulations"]}


def append_regulation(record: dict[str, Any]) -> dict[str, Any]:
    """Add one regulation record to the library (public save helper)."""
    rec = _normalize_record(record)
    lib = _load_library()
    existing = [_hydrate_entry(e) for e in lib.get("regulations", [])]
    lib["regulations"] = _dedupe_regulations(existing + [rec])
    _save_library(lib)
    return rec


def get_regulations(
    *,
    include_text: bool = True,
    category: str | None = None,
    country: str | None = None,
    code: str | None = None,
) -> dict[str, Any]:
    lib = _load_library()
    entries = lib.get("regulations", [])
    if category:
        entries = [e for e in entries if e.get("category") == category.strip()]
    if country:
        c = country.strip().upper()
        entries = [e for e in entries if e.get("country") == c]
    if code:
        c = code.strip()
        entries = [e for e in entries if e.get("reference") == c]
    if not include_text:
        return {"regulations": entries}
    return {"regulations": [_hydrate_entry(e) for e in entries]}


def lookup_stored(
    labels: list[str],
    delivery_countries: list[str],
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """Return regulations already in the library and missing (label, jurisdiction) pairs."""
    labels_norm = sorted({l.strip() for l in labels if l and l.strip()})
    jurisdictions = expand_jurisdictions(delivery_countries)
    lib = get_regulations(include_text=True).get("regulations", [])
    matched: list[dict[str, Any]] = []
    missing: list[tuple[str, str]] = []

    for label in labels_norm:
        if "EU" in jurisdictions:
            hits = [r for r in lib if r.get("category") == label and r.get("country") == "EU"]
            if hits:
                matched.extend(hits)
            else:
                missing.append((label, "EU"))
        if "DE" in jurisdictions:
            if not should_fetch_de(label):
                continue
            hits = [r for r in lib if r.get("category") == label and r.get("country") == "DE"]
            if hits:
                matched.extend(hits)
            else:
                missing.append((label, "DE"))

    return _dedupe_regulations(matched), missing


def regulations_for_labels(
    labels: list[str],
    delivery_countries: list[str],
    *,
    fetch_missing: bool = True,
    save: bool = False,
    product_id: str | None = None,
) -> dict[str, Any]:
    """Load stored regulations and optionally fetch gaps for label × jurisdiction."""
    labels_norm = sorted({l.strip() for l in labels if l and l.strip()})
    matched, missing_pairs = lookup_stored(labels_norm, delivery_countries)
    fetched: list[dict[str, Any]] = []
    missing_info: list[dict[str, str]] = []

    if missing_pairs and fetch_missing:
        missing_labels = sorted({label for label, _ in missing_pairs})
        result = resolve_labels(missing_labels, delivery_countries, product_id=product_id)
        fetched = result.get("regulations", [])
        missing_info = result.get("missing", [])
        if save and fetched:
            lib = _load_library()
            existing = [_hydrate_entry(e) for e in lib.get("regulations", [])]
            lib["regulations"] = _dedupe_regulations(existing + fetched)
            _save_library(lib)

    regulations = _filter_regulations(_dedupe_regulations(matched + fetched))
    return {
        "labels": labels_norm,
        "delivery_countries": delivery_countries,
        "jurisdictions": expand_jurisdictions(delivery_countries),
        "regulations": regulations,
        "missing": missing_info,
        "from_library": len(matched),
        "fetched": len(fetched),
        "count": len(regulations),
    }


def prune_de_transposition_library() -> int:
    """Drop DE EU-transposition ordinances and legacy DE-* duplicate keys."""
    lib = _load_library()
    kept: list[dict[str, Any]] = []
    removed = 0
    preferred_de: dict[tuple[str, str], dict[str, Any]] = {}

    for entry in lib.get("regulations", []):
        rec = _hydrate_entry(entry) if entry.get("file") else _normalize_record(entry)
        if is_de_transposition_record(rec):
            removed += 1
            continue
        cat = str(rec.get("category") or "")
        country = (rec.get("country") or "").upper()
        if country == "DE" and should_fetch_de(cat):
            codes = STREAM_REG_CODES.get(cat)
            preferred_ref = str(codes["de_code"]) if codes else ""
            ref = str(rec.get("reference") or "")
            if preferred_ref and ref != preferred_ref:
                removed += 1
                continue
            key = (cat, country)
            if key in preferred_de:
                removed += 1
                continue
            preferred_de[key] = entry
            kept.append(entry)
            continue
        kept.append(entry)

    lib["regulations"] = kept
    _save_library(lib)
    return removed


def migrate_library() -> dict[str, int]:
    """Rewrite index + per-item JSON files from legacy inline or .txt-backed records."""
    if not REGULATION_LIBRARY_FILE.exists():
        return {"items": 0}
    raw = json.loads(REGULATION_LIBRARY_FILE.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    if isinstance(raw.get("regulations"), list):
        for entry in raw["regulations"]:
            if not isinstance(entry, dict):
                continue
            if entry.get("text") or not entry.get("file"):
                records.append(_normalize_record(entry))
            else:
                records.append(_hydrate_entry(entry))
    lib = {"regulations": _dedupe_regulations(_filter_regulations(records))}
    _save_library(lib)
    return {"items": len(lib["regulations"])}
