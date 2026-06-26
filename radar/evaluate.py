"""Gap evaluation: Applies / Satisfied predicates over organizer Dataset."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from radar.config import CACHE_FILE, FIXTURE_FILE, GAPS_FILE, PARTNERS_FILE, ensure_dirs, load_dotenv

EU_MARKETS = {"EU", "DE", "FR", "NL", "ES", "PL", "IT", "AT", "BE", "SE", "FI", "DK", "IE", "PT", "CZ", "RO", "HU", "SK", "BG", "HR", "LT", "LV", "EE", "SI", "LU", "MT", "CY", "GR"}

BATTERY_DEADLINES = {
    "lmt": "2027-02-18",
    "portable": "2027-02-18",
    "industrial": "2027-08-18",
    "ev": "2026-08-18",
    "button_cell": "2027-02-18",
}

FAMILY_GAP_KEYWORDS: dict[str, list[str]] = {
    "Battery": ["battery passport", "data carrier", "batterie"],
    "RoHS": ["rohs", "lead", "mercury", "dehp", "restricted substance"],
    "REACH": ["reach", "svhc", "pfas", "pfhxa", "coating"],
    "GPSR": ["gpsr", "child access", "button-cell"],
    "RED": ["usb-c", "micro-usb", "common charger", "cybersecurity", "en 18031"],
    "WEEE": ["weee", "producer registration"],
    "ToySafety": ["toy", "dehp"],
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _markets_overlap(product_markets: list[str], partner_sells: list[str], reg_markets: list[str]) -> bool:
    pm = set(product_markets or partner_sells or ["EU"])
    rm = set(reg_markets or ["EU"])
    if "EU" in pm or "EU" in rm:
        return True
    return bool(pm & rm)


def _category_applies(product_cat: str, reg_cats: list[str] | str) -> bool:
    if reg_cats == "all" or reg_cats is None:
        return True
    if isinstance(reg_cats, str):
        return True
    return product_cat in reg_cats


def applies(product: dict, partner: dict, reg: dict) -> bool:
    scope = reg.get("scope", {})
    if not _markets_overlap(product.get("markets", []), partner.get("sells_in", []), scope.get("markets", ["EU"])):
        return False
    if not _category_applies(product.get("category", ""), scope.get("categories", "all")):
        return False

    family = reg.get("regulation_family", "")
    reg_subs = set(scope.get("substances") or [])
    prod_subs = set(product.get("substances") or [])

    if reg_subs and prod_subs & reg_subs:
        return True
    if family == "Battery" and product.get("has_battery"):
        return True
    if family == "RED" and product.get("has_radio"):
        return True
    if family in product.get("compliance_streams", []):
        return True
    if not reg_subs and family in ("Battery", "WEEE", "GPSR", "PPWR", "EnergyLabel"):
        streams = product.get("compliance_streams", [])
        return family in streams or family == "Battery" and product.get("has_battery")
    if scope.get("categories") == "all" and not reg_subs:
        return True
    return False


def _known_gap_matches(known_gaps: list[str], family: str, product: dict, reg: dict) -> bool:
    text = " ".join(known_gaps).lower()
    for kw in FAMILY_GAP_KEYWORDS.get(family, [family.lower()]):
        if kw in text:
            if family == "Battery":
                return product.get("has_battery") and product.get("battery_type") in ("lmt", "portable", "industrial", "ev")
            if family == "RED":
                return product.get("has_radio") or "usb" in text or "charger" in text
            return True
    return False


def _battery_passport_gap(product: dict) -> tuple[bool, str, str]:
    if not product.get("has_battery"):
        return False, "", ""
    btype = product.get("battery_type", "none")
    if btype in ("none",):
        return False, "", ""
    cap = product.get("battery_capacity_wh", 0)
    if btype == "industrial" and cap <= 2000:
        btype = "portable"
    deadline = BATTERY_DEADLINES.get(btype, "2027-02-18")
    gap = f"{btype.upper()} battery sold in the EU with no battery passport / data carrier."
    req = "Batteries must carry a digital battery passport (Art. 77)."
    return True, gap, deadline


def satisfied(product: dict, partner: dict, reg: dict, today: date | None = None) -> tuple[bool, str, str, str]:
    """Returns (satisfied, gap_text, deadline, severity)."""
    today = today or date.today()
    family = reg.get("regulation_family", "")
    status = partner.get("compliance_status", {})
    known = status.get("known_gaps", [])

    if known and _known_gap_matches(known, family, product, reg):
        gap_text = next((g for g in known if any(k in g.lower() for k in FAMILY_GAP_KEYWORDS.get(family, [family.lower()]))), known[0])
        deadline = reg.get("deadline_date") or reg.get("effective_date") or "2027-02-18"
        if family == "Battery":
            _, bgap, bdead = _battery_passport_gap(product)
            if bgap:
                gap_text = bgap
                deadline = bdead
        return False, gap_text, deadline, "high"

    if family == "Battery" and product.get("has_battery"):
        has_gap, gap_text, deadline = _battery_passport_gap(product)
        if has_gap:
            return False, gap_text, deadline, "high"

    reg_subs = set(reg.get("scope", {}).get("substances") or [])
    prod_subs = set(product.get("substances") or [])
    overlap = reg_subs & prod_subs
    if overlap:
        return False, f"Product contains restricted substance(s): {', '.join(sorted(overlap))}.", reg.get("deadline_date", today.isoformat()), "high"

    return True, "", "", "none"


def _format_alert(company: str, product_name: str, regulation: str, deadline: str, action: str, url: str) -> str:
    short_reg = regulation[:40] + "…" if len(regulation) > 40 else regulation
    msg = f"{company}: {product_name} needs {short_reg} by {deadline[:10]}. {action[:40]}. {url[:30]}"
    return msg[:160]


def _build_gap(partner: dict, product: dict, reg: dict, gap: str, deadline: str, severity: str) -> dict:
    family = reg.get("regulation_family", "")
    regulation = reg.get("title") or reg.get("reference", family)
    source_url = reg.get("source_url") or "https://eur-lex.europa.eu"
    action = reg.get("action_required") or f"Address {family} compliance for this product."
    contact = partner.get("contact", {})
    channel = contact.get("preferred_channel", "email")
    to = contact.get("phone") if channel in ("sms", "whatsapp") else contact.get("email", "")

    return {
        "company": partner.get("company", ""),
        "partner_id": partner.get("partner_id", ""),
        "product_id": product.get("product_id", ""),
        "product": product.get("name", ""),
        "regulation": regulation,
        "requirement": reg.get("summary", action),
        "source_url": source_url,
        "gap": gap,
        "deadline": deadline[:10] if deadline else "",
        "severity": severity,
        "recommended_action": action,
        "alert": {
            "channel": channel,
            "to": to,
            "message": _format_alert(
                partner.get("company", "")[:20],
                product.get("name", "")[:30],
                regulation,
                deadline,
                action,
                source_url,
            ),
        },
    }


def evaluate(fixture: Path | None = None) -> list[dict]:
    ensure_dirs()
    load_dotenv()
    partners_data = _load_json(PARTNERS_FILE)
    if fixture:
        updates = _load_json(fixture).get("updates", [])
    else:
        cache = _load_json(CACHE_FILE)
        updates = cache.get("updates", [])

    gaps: list[dict] = []
    for reg in updates:
        for partner in partners_data.get("partners", []):
            for product in partner.get("products", []):
                if not applies(product, partner, reg):
                    continue
                ok, gap_text, deadline, severity = satisfied(product, partner, reg)
                if ok:
                    continue
                gaps.append(_build_gap(partner, product, reg, gap_text, deadline, severity))

    GAPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    GAPS_FILE.write_text(json.dumps(gaps, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return gaps
