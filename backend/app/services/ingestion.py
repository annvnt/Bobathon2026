"""Workflow B (part) — store a fetched regulation in ChromaDB, line by line.

Each sentence/line of the regulation becomes its own vector entry so gap
findings can cite the exact lines (not just a link) and run cause/effect
analysis per line.
"""
from __future__ import annotations

import re

from .. import label_map, vector_store


def _split_lines(text: str) -> list[str]:
    """Split regulation text into sentence-level lines."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.;:])\s+(?=[A-Z0-9])", text)
    return [p.strip() for p in parts if len(p.strip()) > 8]


def _regulation_lines(reg: dict) -> list[str]:
    scope = reg.get("scope", {})
    blocks = [
        reg.get("title", ""),
        f"Reference: {reg.get('reference', '')}.",
        reg.get("summary", ""),
        scope.get("conditions", ""),
        f"Action required: {reg.get('action_required', '')}." if reg.get("action_required") else "",
    ]
    subs = scope.get("substances")
    if subs:
        blocks.append("Substances in scope: " + ", ".join(subs) + ".")
    if reg.get("deadline_date"):
        blocks.append(f"Compliance deadline: {reg.get('deadline_date')}.")
    if reg.get("effective_date"):
        blocks.append(f"Effective date: {reg.get('effective_date')}.")
    lines: list[str] = []
    for block in blocks:
        lines.extend(_split_lines(block))
    # de-dupe while preserving order
    seen, out = set(), []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            out.append(ln)
    return out


def ingest_regulation(reg: dict, country: str) -> int:
    """Chunk into lines + embed + upsert a regulation. Returns #lines stored."""
    label = reg.get("regulation_family", "")
    update_id = reg.get("update_id", f"{label}-{country}")
    lines = _regulation_lines(reg)
    if not lines:
        return 0

    source_url = label_map.source_url(label) or reg.get("source_url", "")
    collection = vector_store.get_collection()
    ids, docs, metas = [], [], []
    for i, line in enumerate(lines):
        ids.append(f"{update_id}::L{i}")
        docs.append(line)
        metas.append({
            "label": label,
            "country": country,
            "update_id": update_id,
            "line_no": i + 1,
            "date_added": reg.get("published_date", ""),
            "deadline": reg.get("deadline_date", "") or "",
            "severity": reg.get("severity", "medium"),
            "title": reg.get("title", ""),
            "reference": reg.get("reference", ""),
            "source_url": source_url,
        })
    collection.upsert(ids=ids, documents=docs, metadatas=metas)
    return len(lines)
