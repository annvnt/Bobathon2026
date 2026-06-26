"""Format structured alerts per product plan §6.2."""

from __future__ import annotations

from typing import Any

CRITICALITY_LABEL = {"critical": "Critical", "moderate": "Moderate", "administrative": "Administrative"}
URGENCY_LABEL = {
    "immediate": "Act now",
    "short_term": "Act within weeks",
    "medium_term": "Plan now",
    "long_term": "Schedule",
}


def format_platform_alert(gap: dict) -> str:
    """Full structured alert for platform / email."""
    crit = CRITICALITY_LABEL.get(gap.get("criticality", ""), gap.get("criticality", ""))
    urg = URGENCY_LABEL.get(gap.get("urgency", ""), gap.get("urgency", ""))
    actions = gap.get("action_items") or []
    action_lines = "\n".join(
        f"  {a.get('step', i+1)}. {a.get('action', '')} ({a.get('owner', 'TBD')})"
        for i, a in enumerate(actions)
    )
    return f"""[{crit}] [{urg}] — Regulatory Radar

Company:      {gap.get('company', '')}
Product:      {gap.get('product', '')} ({gap.get('product_category', '')})
Regulation:   {gap.get('regulation', '')}
Deadline:     {gap.get('deadline', '')} · {gap.get('days_remaining', '?')} days remaining

WHAT IS REQUIRED
{gap.get('requirement', '')}

THE GAP
{gap.get('gap', '')}

WHY THIS APPLIES TO YOU
{gap.get('why_applies', '')}

CONSEQUENCES IF IGNORED
{gap.get('consequences', '')}

ACTIONS REQUIRED (in order)
{action_lines}

Source:       {gap.get('source_url', '')} · fetched {gap.get('fetched_at', 'n/a')}
Confidence:   {gap.get('confidence_score', 0)}%

Reply HELP to speak to an EcoComply compliance expert."""


def format_sms_alert(gap: dict, base_url: str = "http://127.0.0.1:8000") -> str:
    """Compressed SMS ≤300 chars with link hint."""
    crit = gap.get("criticality", "moderate")[:4].upper()
    days = gap.get("days_remaining", "?")
    reg = (gap.get("regulation") or "")[:35]
    product = (gap.get("product") or "")[:25]
    msg = (
        f"[{crit}] {gap.get('company', '')[:18]}: {product} — {reg}… "
        f"{days}d left. {base_url}/#gaps-section"
    )
    return msg[:300]


def attach_alert_payload(gap: dict) -> dict[str, Any]:
    """Build alert sub-object on a gap record."""
    channel = gap.get("alert", {}).get("channel", "email")
    full = format_platform_alert(gap)
    sms = format_sms_alert(gap)
    message = sms if channel in ("sms", "whatsapp") else full
    return {
        "channel": channel,
        "to": gap.get("alert", {}).get("to", ""),
        "message": message,
        "message_full": full,
        "message_sms": sms,
    }
