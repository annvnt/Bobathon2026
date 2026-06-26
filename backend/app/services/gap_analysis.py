"""Workflows B + C — daily sync, RAG gap analysis, alert generation.

run_sync():
  1. check_updates()                     (MCP — teammate's domain)
  2. for each changed label/country:
       fetch_regulation()                (MCP — teammate's domain)
       ingest_regulation() -> ChromaDB   (Workflow B)
       assess_products()                 (Workflow C: match -> RAG -> LLM -> alert)
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import label_map, models, vector_store
from ..schemas import ScanResult
from . import alerts as alert_sender
from . import impact as impact_svc
from . import mock_mcp
from .ingestion import ingest_regulation
from .llm import get_llm

logger = logging.getLogger("ecocomply.sync")

# Pluggable MCP — replace with the real MCP client when available.
mcp = mock_mcp


# --------------------------------------------------------------------------- #
# Applicability (structured scope matching)
# --------------------------------------------------------------------------- #
def _markets_overlap(product_markets: list[str], scope_markets: list[str]) -> bool:
    if not scope_markets:
        return True
    if "EU" in scope_markets or "EU" in product_markets:
        # EU rule applies to anyone selling in the EU / any member state.
        return "EU" in product_markets or bool(
            set(product_markets) & set(scope_markets)
        ) or "EU" in scope_markets and bool(product_markets)
    return bool(set(product_markets) & set(scope_markets))


def _applies(product: models.Product, reg: dict) -> tuple[bool, str]:
    """Structured scope check. Returns (applies, reason). Catches look-alikes."""
    scope = reg.get("scope", {})

    # Market
    if not _markets_overlap(product.markets or [], scope.get("markets", [])):
        return False, "Market exclusion — product not sold where this rule applies."

    # Category
    cats = scope.get("categories", "all")
    if cats != "all" and isinstance(cats, list) and cats:
        if product.category not in cats:
            return False, f"Category '{product.category}' is out of scope."

    # Substance — if the rule names substances, the product must contain one.
    scope_subs = scope.get("substances", [])
    if scope_subs:
        if not (set(product.substances or []) & set(scope_subs)):
            return False, (
                "Substance not present — rule targets "
                + ", ".join(scope_subs)
                + " which this product does not contain."
            )

    return True, "In scope: market, category and substance criteria all match."


# --------------------------------------------------------------------------- #
# RAG retrieval
# --------------------------------------------------------------------------- #
def _retrieve_chunks(product: models.Product, label: str, k: int = 3) -> list[str]:
    query = (
        f"{product.name}. {product.description}. "
        f"Substances: {', '.join(product.substances or [])}. "
        f"Category: {product.category}."
    )
    try:
        res = vector_store.get_collection().query(
            query_texts=[query],
            n_results=k,
            where={"label": label},
        )
        docs = res.get("documents") or [[]]
        return docs[0] if docs else []
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG query failed: %s", exc)
        return []


# --------------------------------------------------------------------------- #
# Gap evaluation (LLM with offline fallback)
# --------------------------------------------------------------------------- #
_GAP_SYSTEM = (
    "You are an EU product-compliance analyst. Given a product and the cited "
    "lines of a current regulation, decide whether the product has a compliance "
    "gap, then explain it line by line with cause and effect plus product and "
    "business impact. Be strict: only report a gap that genuinely applies."
)


def _gap_prompt(product: models.Product, reg: dict, lines: list[str]) -> str:
    numbered = "\n".join(f"  [{i}] {ln}" for i, ln in enumerate(lines))
    return f"""PRODUCT:
- name: {product.name}
- category: {product.category}
- substances: {product.substances}
- has_battery: {product.has_battery} (type {product.battery_type}, {product.battery_capacity_wh} Wh)
- has_radio: {product.has_radio}
- intended_use: {product.intended_use}
- markets: {product.markets}

REGULATION ({reg.get('regulation_family')} — {reg.get('reference')}):
{reg.get('summary')}

CITED REGULATION LINES (analyze each by its index):
{numbered}

Decide if this product has a compliance gap. For EACH cited line, give a cause
(what the line requires) and an effect (what it means for THIS product, citing the
specific attribute that triggers it). Then give an overall product impact and
business impact. Output ONLY JSON:
{{
  "has_gap": true/false,
  "gap": "<1-2 sentence specific gap>",
  "reasoning": "<which attribute triggers it>",
  "confidence": 0-100,
  "product_impact": "<what this product must change>",
  "business_impact": "<commercial consequence: fines, market ban, cost>",
  "line_analysis": [{{"index": 0, "cause": "<...>", "effect": "<...>"}}]
}}"""


def _evaluate_gap(product: models.Product, reg: dict, lines: list[str], reason: str) -> dict:
    raw = get_llm().complete_json(_gap_prompt(product, reg, lines), system=_GAP_SYSTEM)
    return {
        "has_gap": bool(raw.get("has_gap", False)),
        "gap": raw.get("gap", ""),
        "reasoning": raw.get("reasoning", reason),
        "confidence": int(raw.get("confidence", 80) or 80),
        "product_impact": raw.get("product_impact", ""),
        "business_impact": raw.get("business_impact", ""),
        "line_analysis": raw.get("line_analysis", []) or [],
    }


# --------------------------------------------------------------------------- #
# Alert composition
# --------------------------------------------------------------------------- #
def _build_message(product: models.Product, company: str, reg: dict, gap: str) -> str:
    deadline = reg.get("deadline_date") or "—"
    return (
        f"{company}: your {product.name} must meet "
        f"{reg.get('reference')} by {deadline}. {gap} "
        f"Action: {reg.get('action_required', 'Review and remediate.')} "
        f"Source: {reg.get('source_url', '')}"
    )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def assess_products_for_regulation(db: Session, reg: dict, country: str) -> int:
    """Workflow C for a single regulation. Returns number of alerts created."""
    label = reg.get("regulation_family", "")
    update_id = reg.get("update_id", "")
    products = db.execute(
        select(models.Product).where(
            models.Product.compliance_streams.isnot(None)
        )
    ).scalars().all()
    # filter in Python: compliance_streams is a JSON array
    targets = [p for p in products if label in (p.compliance_streams or [])]

    created = 0
    for product in targets:
        applies, reason = _applies(product, reg)
        if not applies:
            logger.info("SKIP %s vs %s: %s", product.name, label, reason)
            continue

        # dedupe: same product + same update already alerted
        dup = db.execute(
            select(models.Alert).where(
                models.Alert.product_id == product.id,
                models.Alert.regulation_label == label,
                models.Alert.regulation_title == reg.get("title", ""),
            )
        ).scalars().first()
        if dup:
            continue

        lines = _retrieve_chunks(product, label, k=4)
        verdict = _evaluate_gap(product, reg, lines, reason)
        if not verdict.get("has_gap"):
            continue

        company = product.user.company_name if product.user else ""
        message = _build_message(product, company, reg, verdict["gap"])

        # Line-by-line citations + cause/effect (LLM) + product/business impact + dates.
        citations = impact_svc.build_citations(
            product, reg, lines, verdict.get("line_analysis")
        )
        key_dates: list[str] = []
        for c in citations:
            for d in c["dates"]:
                if d not in key_dates:
                    key_dates.append(d)
        for d in (reg.get("deadline_date"), reg.get("effective_date")):
            if d and d not in key_dates:
                key_dates.append(d)
        source_url = label_map.source_url(label) or reg.get("source_url", "")

        alert = models.Alert(
            product_id=product.id,
            regulation_label=label,
            regulation_title=reg.get("title", ""),
            requirement=reg.get("summary", ""),
            gap=verdict["gap"],
            recommended_action=reg.get("action_required", ""),
            severity=reg.get("severity", "medium"),
            deadline=reg.get("deadline_date") or None,
            source_url=source_url,
            confidence=verdict.get("confidence", 80),
            alert_message=message,
            citations=citations,
            product_impact=verdict.get("product_impact") or impact_svc.product_impact(label, product),
            business_impact=verdict.get("business_impact") or impact_svc.business_impact(reg.get("severity", "medium")),
            key_dates=key_dates,
        )

        # fire the notification
        channel = "sms"
        to = ""
        if product.user:
            # contact details aren't stored on the user model; use test number
            channel = "sms"
        result = alert_sender.send_alert(to=to, body=message, channel=channel)
        alert.delivery_status = result["status"]

        db.add(alert)
        created += 1

    db.commit()
    logger.info("Regulation %s/%s: %d alerts from %d in-scope products",
                label, country, created, len(targets))
    return created


def run_sync(db: Session) -> ScanResult:
    """Full daily sync (Workflows B + C)."""
    updates = mcp.check_updates()
    logger.info("check_updates -> %s", updates)

    total_alerts = 0
    assessed = 0
    labels = []
    for item in updates:
        label, country = item["label"], item["country"]
        reg = mcp.fetch_regulation(label, country)
        if not reg:
            continue
        labels.append(label)
        ingest_regulation(reg, country)
        total_alerts += assess_products_for_regulation(db, reg, country)
        assessed += 1

    return ScanResult(
        updated_labels=labels,
        products_assessed=assessed,
        alerts_created=total_alerts,
        message=(
            f"Synced {len(labels)} regulation update(s); "
            f"created {total_alerts} new alert(s)."
        ),
    )
