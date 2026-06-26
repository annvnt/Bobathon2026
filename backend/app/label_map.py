"""Parses Dataset/labels.md — the single source of truth for automated labeling.

The classifier emits ONLY labels defined here, and gap citations use each label's
source URL / regulation reference from this file. Editing labels.md changes
behaviour with no code change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from .config import settings


@dataclass
class LabelDef:
    label: str
    regulation: str
    source: str
    source_url: str
    triggers: list[str] = field(default_factory=list)


def _parse_triggers(cell: str) -> list[str]:
    return [t.strip() for t in cell.split() if t.strip()]


@lru_cache
def load_labels() -> dict[str, LabelDef]:
    path = settings.dataset_dir / "labels.md"
    out: dict[str, LabelDef] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return out

    # Grab the section after "## Labels (machine-readable)"
    marker = text.find("## Labels")
    section = text[marker:] if marker != -1 else text

    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        label = cells[0]
        # skip header + separator rows
        if label.lower() == "label" or set(label) <= {"-", ":"}:
            continue
        out[label] = LabelDef(
            label=label,
            regulation=cells[1],
            source=cells[2],
            source_url=cells[3],
            triggers=_parse_triggers(cells[4]),
        )
    return out


def all_labels() -> list[str]:
    return list(load_labels().keys())


def get(label: str) -> LabelDef | None:
    return load_labels().get(label)


def source_url(label: str) -> str:
    d = get(label)
    return d.source_url if d else ""


def regulation_ref(label: str) -> str:
    d = get(label)
    return d.regulation if d else label


def _matches(token: str, *, category: str, substances: list[str], has_battery: bool,
             has_radio: bool, intended_use: str, packaging: list[str]) -> bool:
    if token == "eee":
        return category != "" and category != "cable"
    if token == "battery":
        return has_battery
    if token == "radio":
        return has_radio
    if token == "packaging":
        return bool(packaging)
    if token in {"consumer", "toy", "medical", "industrial"}:
        return intended_use == token
    if token.startswith("substance:"):
        wanted = {s.strip() for s in token.split(":", 1)[1].split(",")}
        return bool(wanted & set(substances or []))
    if token.startswith("category:"):
        wanted = {c.strip() for c in token.split(":", 1)[1].split(",")}
        return category in wanted
    return False


def labels_for_product(
    *,
    category: str,
    substances: list[str],
    has_battery: bool,
    has_radio: bool,
    intended_use: str,
    packaging: list[str],
) -> list[str]:
    """Return the labels (from labels.md) that attach to this product."""
    result: list[str] = []
    for label, ldef in load_labels().items():
        if any(
            _matches(
                tok,
                category=category,
                substances=substances,
                has_battery=has_battery,
                has_radio=has_radio,
                intended_use=intended_use,
                packaging=packaging,
            )
            for tok in ldef.triggers
        ):
            result.append(label)
    return result
