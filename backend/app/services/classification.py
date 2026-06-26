"""Workflow A — product classification / labeling (LLM-only, via OpenRouter).

Given a free-text product description, the LLM predicts category, substances,
battery/radio attributes, markets and intended use. Labels (compliance streams)
are then derived purely from labels.md so only mapped labels are ever assigned.
"""
from __future__ import annotations

from .. import label_map, taxonomy
from ..schemas import ClassifyResult
from .llm import get_llm

SYSTEM_PROMPT = (
    "You are a regulatory compliance classifier for electronics products sold "
    "in the EU. You map a product description onto a controlled taxonomy. You are "
    "precise and never invent categories or substances outside the provided lists."
)


def _build_prompt(description: str) -> str:
    cats = "\n".join(f"  - {k}: {v}" for k, v in taxonomy.categories().items())
    subs = "\n".join(f"  - {k}: {v}" for k, v in taxonomy.substances().items())
    return f"""Analyze this product description and classify it.

PRODUCT DESCRIPTION:
\"\"\"{description}\"\"\"

ALLOWED CATEGORIES (pick exactly one key):
{cats}

ALLOWED SUBSTANCES (pick zero or more keys actually likely present):
{subs}

Determine:
- name: a short product name (infer from the description)
- category: one category key from the list
- substances: list of substance keys actually likely present
- has_battery: true/false
- battery_type: one of none|portable|button_cell|lmt|industrial
- battery_capacity_wh: number (0 if no battery)
- has_radio: true/false (Bluetooth/Wi-Fi/cellular/RF)
- intended_use: one of consumer|toy|industrial|medical
- markets: ISO codes, use ["EU"] if it targets the EU broadly
- reasoning: one sentence on the classification

Output ONLY a JSON object with exactly these keys."""


def derive_compliance_streams(
    *,
    category: str,
    substances: list[str],
    has_battery: bool,
    has_radio: bool,
    intended_use: str,
    markets: list[str],
    packaging: list[str],
) -> list[str]:
    """Derive compliance labels purely from labels.md (single source of truth)."""
    return label_map.labels_for_product(
        category=category,
        substances=substances,
        has_battery=has_battery,
        has_radio=has_radio,
        intended_use=intended_use,
        packaging=packaging,
    )


def _finalize(result: ClassifyResult) -> ClassifyResult:
    valid_cats = set(taxonomy.categories())
    valid_subs = set(taxonomy.substances())
    if result.category not in valid_cats:
        result.category = "appliance" if "appliance" in valid_cats else next(iter(valid_cats), "")
    result.substances = [s for s in result.substances if s in valid_subs]
    if not result.markets:
        result.markets = ["EU"]
    # Labels come PURELY from labels.md.
    result.compliance_streams = derive_compliance_streams(
        category=result.category,
        substances=result.substances,
        has_battery=result.has_battery,
        has_radio=result.has_radio,
        intended_use=result.intended_use,
        markets=result.markets,
        packaging=["cardboard"],
    )
    return result


def classify(description: str, name: str | None = None) -> ClassifyResult:
    raw = get_llm().complete_json(_build_prompt(description), system=SYSTEM_PROMPT)
    result = ClassifyResult(
        name=name or raw.get("name", ""),
        category=raw.get("category", ""),
        substances=raw.get("substances", []) or [],
        has_battery=bool(raw.get("has_battery", False)),
        battery_type=raw.get("battery_type", "none") or "none",
        battery_capacity_wh=float(raw.get("battery_capacity_wh", 0) or 0),
        has_radio=bool(raw.get("has_radio", False)),
        intended_use=raw.get("intended_use", "consumer") or "consumer",
        markets=raw.get("markets", ["EU"]) or ["EU"],
        reasoning=raw.get("reasoning", "Classified by LLM."),
    )
    return _finalize(result)
