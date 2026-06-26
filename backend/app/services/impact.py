"""Cause/effect + product & business impact analysis for cited regulation lines.

Turns the raw regulation lines retrieved from the vector DB into structured
citations: each line gets a plain-language cause, an effect on this specific
product, product- and business-level impact, and any dates extracted from it.

Uses the LLM when configured; otherwise deterministic heuristics keyed off the
label, severity and product attributes.
"""
from __future__ import annotations

import re

from .. import label_map, models

# --------------------------------------------------------------------------- #
# Date extraction
# --------------------------------------------------------------------------- #
_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|"
    "november|december"
)
_DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                       # 2027-02-18
    re.compile(rf"\b\d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}}\b", re.I),  # 18 February 2027
    re.compile(rf"\b(?:{_MONTHS})\s+\d{{4}}\b", re.I),          # February 2027
    re.compile(r"\b(?:by|from|before|until)\s+\d{4}\b", re.I),  # by 2027
]


def extract_dates(text: str) -> list[str]:
    found: list[str] = []
    for pat in _DATE_PATTERNS:
        for m in pat.finditer(text or ""):
            val = m.group(0)
            if val not in found:
                found.append(val)
    return found


# --------------------------------------------------------------------------- #
# Impact heuristics
# --------------------------------------------------------------------------- #
_BUSINESS_IMPACT = {
    "high": (
        "Fines up to €100k+ per market and possible market ban or marketplace "
        "delisting. Direct revenue and brand exposure."
    ),
    "medium": (
        "Warning notices and a required corrective-action plan; potential product "
        "recall if unaddressed. Remediation cost and management time."
    ),
    "low": (
        "Administrative or registration penalty and a reporting deadline on record. "
        "Low direct cost but an audit-trail liability."
    ),
}

_PRODUCT_ACTION = {
    "RoHS": "Re-test homogeneous materials and re-issue the EU Declaration of Conformity.",
    "REACH": "Check the SVHC concentration per article and notify SCIP / downstream users.",
    "WEEE": "Register as a producer and mark the product with the crossed-out wheelie bin.",
    "Battery": "Create the battery passport / data carrier and meet removability + labelling.",
    "PPWR": "Classify packaging, assess recyclability and register with the national EPR scheme.",
    "GPSR": "Complete a risk assessment, appoint an EU representative and maintain the technical file.",
    "RED": "Meet the harmonised radio standards (incl. cybersecurity EN 18031) and update the DoC.",
    "EMC": "Re-verify electromagnetic compatibility against the harmonised standards.",
    "LVD": "Re-verify low-voltage safety against the harmonised standards.",
    "ESPR": "Prepare the Digital Product Passport and meet the ecodesign requirements.",
    "EnergyLabel": "Register the model in EPREL and attach the correct energy label.",
    "ToySafety": "Complete toy-safety conformity assessment and CE marking.",
    "MDR": "Meet medical-device conformity and clinical documentation requirements.",
    "POPs": "Verify POP substance content is below the limit and document the supply chain.",
    "Machinery": "Complete the machinery conformity assessment and technical file.",
}


def business_impact(severity: str) -> str:
    return _BUSINESS_IMPACT.get(severity, _BUSINESS_IMPACT["medium"])


def product_impact(label: str, product: models.Product) -> str:
    action = _PRODUCT_ACTION.get(label, "Review the obligation and update technical documentation.")
    return f"For {product.name} ({product.category.replace('_', ' ')}): {action}"


# --------------------------------------------------------------------------- #
# Per-line cause/effect
# --------------------------------------------------------------------------- #
def _effect_for_line(line: str, product: models.Product, label: str) -> str:
    triggers = []
    subs = set(product.substances or [])
    line_l = line.lower()
    for s in subs:
        if s.lower() in line_l:
            triggers.append(f"this product contains {s}")
    if product.has_battery and "batter" in line_l:
        triggers.append(
            f"it has a {product.battery_type} battery ({product.battery_capacity_wh} Wh)"
        )
    if product.has_radio and ("radio" in line_l or "wireless" in line_l):
        triggers.append("it includes a radio module")
    if not triggers:
        triggers.append(f"it is in scope as {product.category.replace('_', ' ')}")
    return (
        "Because " + ", and ".join(triggers) + ", "
        f"{product.name} must satisfy this clause before being placed on the EU market."
    )


def build_citations(
    product: models.Product,
    reg: dict,
    lines: list[str],
    line_analysis: list[dict] | None = None,
) -> list[dict]:
    """Construct line-by-line citations with cause/effect + dates.

    Uses the LLM's per-line analysis when provided; otherwise falls back to a
    deterministic heuristic so a citation always carries a cause and effect.
    """
    label = reg.get("regulation_family", "")
    src = label_map.source_url(label) or reg.get("source_url", "")
    ref = reg.get("reference", "")
    by_index = {a.get("index"): a for a in (line_analysis or []) if isinstance(a, dict)}

    citations: list[dict] = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        a = by_index.get(i, {})
        cause = a.get("cause") or f"The regulation requires: “{line}”"
        effect = a.get("effect") or _effect_for_line(line, product, label)
        citations.append({
            "line_no": i + 1,
            "text": line,
            "reference": ref,
            "source_url": src,
            "cause": cause,
            "effect": effect,
            "dates": extract_dates(line),
        })
    return citations
