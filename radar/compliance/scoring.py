"""Criticality, urgency, confidence, and reasoning for compliance findings."""

from __future__ import annotations

from datetime import date
from typing import Any

CONSEQUENCES = {
    "critical": (
        "€100k+ fine per market · Market ban with no grace period · "
        "Marketplace delisting · Brand damage"
    ),
    "moderate": (
        "Warning notice from market authority · Required corrective action plan · "
        "Potential product recall"
    ),
    "administrative": (
        "Registration fee or administrative penalty · "
        "Reporting deadline missed on record"
    ),
}

URGENCY_COPY = {
    "immediate": "Your product is non-compliant right now. Every day without action is a day of exposure.",
    "short_term": "You have {days} days. Most remediation steps take 4–8 weeks minimum.",
    "medium_term": "Deadline is in {months} months. Start scoping now to avoid a last-minute scramble.",
    "long_term": "Deadline is {date}. Add to your compliance roadmap — not urgent but must not be forgotten.",
}


def days_until(deadline: str, today: date | None = None) -> int:
    today = today or date.today()
    try:
        dl = date.fromisoformat(deadline[:10])
    except ValueError:
        return 365
    return (dl - today).days


def score_urgency(deadline: str, family: str, today: date | None = None) -> tuple[str, str]:
    """Return (urgency_level, urgency_message)."""
    days = days_until(deadline, today)
    in_force_now = family in ("RoHS", "REACH", "GPSR", "WEEE") and days > 365

    if days <= 0 or in_force_now:
        level = "immediate"
        msg = URGENCY_COPY["immediate"]
    elif days < 90:
        level = "short_term"
        msg = URGENCY_COPY["short_term"].format(days=days)
    elif days < 365:
        level = "medium_term"
        msg = URGENCY_COPY["medium_term"].format(months=max(1, days // 30))
    else:
        level = "long_term"
        msg = URGENCY_COPY["long_term"].format(date=deadline[:10])

    return level, msg


def score_criticality(severity: str, family: str) -> tuple[str, str]:
    """Map legacy severity to product-plan criticality level."""
    sev = (severity or "medium").lower()
    if sev in ("critical", "high") or family in ("Battery", "REACH", "RoHS"):
        if sev == "low":
            return "administrative", CONSEQUENCES["administrative"]
        if family in ("WEEE", "PPWR") and sev not in ("critical", "high"):
            return "moderate", CONSEQUENCES["moderate"]
        return "critical", CONSEQUENCES["critical"]
    if sev == "medium":
        return "moderate", CONSEQUENCES["moderate"]
    return "administrative", CONSEQUENCES["administrative"]


def score_confidence(
    product: dict,
    partner: dict,
    reg: dict,
    *,
    from_known_gap: bool,
    substance_match: bool,
) -> int:
    if from_known_gap:
        return 95
    if substance_match:
        return 88
    if product.get("has_battery") and reg.get("regulation_family") == "Battery":
        cap = product.get("battery_capacity_wh", 0)
        if cap > 2000 or product.get("battery_type") in ("lmt", "portable", "industrial", "ev"):
            return 85
        return 72
    if reg.get("router_confidence"):
        return int(reg["router_confidence"])
    return 68


def build_reasoning(product: dict, partner: dict, reg: dict, gap: str) -> tuple[str, str]:
    """Return (why_applies, reasoning trace)."""
    family = reg.get("regulation_family", "")
    markets = product.get("markets") or partner.get("sells_in", ["EU"])
    parts: list[str] = []
    why: list[str] = []

    if family == "Battery" and product.get("has_battery"):
        cap = product.get("battery_capacity_wh", 0)
        btype = product.get("battery_type", "unknown")
        why.append(
            f"Product has a {cap}Wh {btype} battery sold in {', '.join(markets)} — "
            f"EU Battery Regulation 2023/1542 requires a digital passport for this battery type."
        )
        if cap > 2000:
            why.append(f"Battery capacity {cap}Wh exceeds common passport thresholds (Art. 77).")

    elif family == "REACH":
        subs = set(product.get("substances") or []) & set(reg.get("scope", {}).get("substances") or [])
        if subs:
            why.append(
                f"Product substances {', '.join(sorted(subs))} overlap ECHA SVHC / restriction scope."
            )

    elif family == "RoHS":
        why.append(
            f"Category '{product.get('category')}' EEE sold in EU — RoHS substance restrictions apply."
        )

    elif family == "RED" and product.get("has_radio"):
        why.append(f"Product has radio module — RED 2014/53/EU obligations apply.")

    elif family == "WEEE" and "DE" in markets:
        why.append(f"EEE product sold in Germany — ElektroG producer registration required.")

    elif family == "GPSR" and product.get("intended_use") == "consumer":
        why.append("Consumer product in EU market — GPSR 2023/988 safety obligations apply.")

    else:
        why.append(
            f"Product attributes match {family} scope for markets {', '.join(markets)}."
        )

    # Market exclusion note (false-positive demo case)
    non_eu_only = markets and not (set(markets) & {"EU", "DE", "FR", "NL", "ES", "IT", "PL", "AT", "BE"})
    if non_eu_only:
        parts.append("Market exclusion: product markets do not include EU — verify scope manually.")

    reasoning = " ".join(why) if why else gap
    why_applies = why[0] if why else f"This regulation applies because: {gap}"
    if parts:
        reasoning = f"{reasoning} {' '.join(parts)}"
    return why_applies, reasoning


def initial_status(confidence: int, criticality: str, threshold: int = 70) -> str:
    if confidence >= threshold:
        return "auto_alerted"
    return "in_review"
