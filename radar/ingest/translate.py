"""Normalize raw API records into regulatory_updates schema."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Any

from radar.compliance import taxonomy

ISO_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def dedup_key(source: str, doc_ref: str, effective: str) -> str:
    raw = f"{source}|{doc_ref}|{effective}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _today() -> str:
    return date.today().isoformat()


def _pick_date(*candidates: str | None, fallback: str | None = None) -> str:
    for c in candidates:
        if not c:
            continue
        m = ISO_DATE.search(str(c))
        if m:
            return m.group(1)
    return fallback or _today()


def from_eurlex(hit: dict[str, Any]) -> dict[str, Any]:
    celex = hit.get("celex", "")
    title = hit.get("title", "EUR-Lex document")
    text = f"{title} {hit.get('reference', '')} {celex}"
    family = taxonomy.detect_family(text)
    eff = _pick_date(hit.get("applicable_date"), hit.get("published_date"))
    doc_url = hit.get("url") or f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
    return _base_record(
        source="EUR-Lex",
        family=family,
        reference=hit.get("reference") or f"CELEX {celex}",
        title=title,
        summary=hit.get("summary") or title,
        effective=eff,
        url=doc_url,
        text=text,
        change_type=hit.get("change_type", "new"),
    )


def from_oj_rss(hit: dict[str, Any]) -> dict[str, Any]:
    """Official Journal RSS item — acts, corrigenda, amendments."""
    celex = hit.get("celex", "")
    title = hit.get("title") or f"OJ act {celex}"
    series = hit.get("oj_series", "L")
    text = f"{title} {celex} OJ-{series}"
    family = taxonomy.detect_family(text)
    eff = _pick_date(hit.get("published_date"), hit.get("pub_datetime"))
    doc_url = hit.get("url") or f"https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:{celex}"
    summary = hit.get("summary") or title
    if hit.get("oj_series"):
        summary = f"[OJ {hit['oj_series']}] {summary}"
    return _base_record(
        source="EU Official Journal",
        family=family,
        reference=celex,
        title=title,
        summary=summary,
        effective=eff,
        url=doc_url,
        text=text,
        change_type=hit.get("change_type", "new"),
    )


def from_dip(doc: dict[str, Any]) -> dict[str, Any]:
    title = doc.get("titel", "Bundestag legislative process")
    doc_id = doc.get("id", "")
    datum = doc.get("datum", _today())
    drucksache = ""
    for d in doc.get("drucksache", []) or []:
        drucksache = d.get("dokumentnummer", drucksache)
    text = f"{title} {drucksache}"
    family = taxonomy.detect_family(text)
    url = f"https://dip.bundestag.de/vorgang/{doc_id}" if doc_id else "https://dip.bundestag.de"
    return _base_record(
        source="Bundestag",
        family=family,
        reference=drucksache or doc_id,
        title=title,
        summary=f"German parliamentary process: {title}",
        effective=datum,
        url=url,
        text=text,
        change_type="new",
    )


def from_openlegaldata(item: dict[str, Any]) -> dict[str, Any]:
    book_code = item.get("book_code") or ""
    title = item.get("title") or item.get("section") or book_code
    section = item.get("section") or ""
    full_title = f"{book_code} {section} {title}".strip()
    doc_id = item.get("id", "")
    doknr = item.get("doknr") or str(doc_id)
    eff = _pick_date(item.get("updated_date"), item.get("created_date"))
    text = f"{full_title} {book_code} {doknr}"
    family = taxonomy.detect_family(text)
    slug = item.get("book_slug") or ""
    url = f"https://de.openlegaldata.io/laws/{doc_id}/" if doc_id else "https://de.openlegaldata.io"
    return _base_record(
        source="OpenLegalData",
        family=family,
        reference=doknr,
        title=full_title or book_code,
        summary=f"German law norm from Open Legal Data: {book_code} {section}".strip(),
        effective=eff,
        url=url,
        text=text,
        change_type="new",
    )


def from_echa(name_or_entry: str | dict[str, Any], list_type: str | None = None, restriction_date: str | None = None) -> dict[str, Any]:
    if isinstance(name_or_entry, dict):
        entry = name_or_entry
        name = entry["name"]
        list_type = entry.get("list_kind", list_type or "candidate_list").replace("_", " ")
        restriction_date = entry.get("effective_date") or restriction_date
        substances = entry.get("substances") or list(taxonomy.resolve_substances(name))
        url = entry.get("url") or "https://echa.europa.eu/candidate-list-table"
        reference = entry.get("reference") or f"ECHA {list_type}: {name}"
        summary = (
            f"{entry.get('summary_extra', '')} Substance listed: {name}."
            + (f" Entry {entry['entry_number']}." if entry.get("entry_number") else "")
        ).strip()
        family = "REACH"
        if "restriction" in str(entry.get("list_kind", "")):
            family = "REACH"
        text = f"{name} {entry.get('cas_number', '')} {entry.get('ec_number', '')} {list_type}"
    else:
        name = name_or_entry
        list_type = list_type or "candidate_list"
        text = f"{name} {list_type} REACH SVHC restriction"
        family = "REACH" if "svhc" in list_type.lower() or "candidate" in list_type.lower() else "RoHS"
        substances = list(taxonomy.resolve_substances(name))
        if not substances:
            substances = list(taxonomy.resolve_substances(text))
        url = "https://echa.europa.eu/candidate-list-table"
        reference = f"ECHA {list_type}: {name}"
        summary = f"Substance {name} listed on ECHA {list_type}."

    eff = restriction_date or _today()
    return _base_record(
        source="ECHA",
        family=family,
        reference=reference,
        title=f"ECHA {list_type.replace('_', ' ')} — {name[:100]}",
        summary=summary,
        effective=eff,
        url=url,
        text=text,
        change_type="new",
        substances=substances,
    )


def _base_record(
    *,
    source: str,
    family: str,
    reference: str,
    title: str,
    summary: str,
    effective: str,
    url: str,
    text: str,
    change_type: str,
    substances: list[str] | None = None,
) -> dict[str, Any]:
    subs = substances if substances is not None else list(taxonomy.resolve_substances(text))
    cats = taxonomy.detect_categories(text)
    ref = reference or title
    return {
        "update_id": f"{source[:3].upper()}-{hashlib.md5(ref.encode()).hexdigest()[:8]}",
        "published_date": effective,
        "source": source,
        "regulation_family": family,
        "reference": reference,
        "title": title,
        "summary": summary,
        "change_type": change_type,
        "effective_date": effective,
        "deadline_date": effective,
        "severity": "medium",
        "action_required": f"Review {family} obligations for affected products.",
        "source_url": url,
        "scope": {
            "categories": cats,
            "substances": subs,
            "markets": ["EU"],
            "conditions": summary,
        },
        "dedup_key": dedup_key(source, ref, effective),
    }
