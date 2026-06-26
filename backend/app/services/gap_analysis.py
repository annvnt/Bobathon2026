"""Workflows B + C — daily sync, RAG gap analysis, alert generation.

run_sync():
  1. check_updates()                     (MCP — teammate's domain)
  2. for each changed label/country:
       fetch_regulation()                (MCP — teammate's domain)
       ingest_regulation() -> ChromaDB   (Workflow B)
       assess_products()                 (Workflow C: match -> RAG -> LLM -> alert)
"""
from __future__ import annotations

from datetime import datetime, date
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session

# Parallel LLM gap-evaluation workers per regulation (OpenRouter handles concurrency).
_GAP_WORKERS = 12

from .. import label_map, models, vector_store
from ..config import settings
from ..schemas import ScanResult
from . import alerts as alert_sender
from . import impact as impact_svc
from .ingestion import ingest_regulation
from .llm import get_llm

logger = logging.getLogger("ecocomply.sync")

# Connect to the real team MCP (radar.mcp.contract); fall back to the bundled
# dataset mock only if radar is unavailable.
try:
    from . import mcp_client as mcp
    logger.info("MCP: connected to radar.mcp.contract")
except Exception as exc:  # noqa: BLE001
    from . import mock_mcp as mcp
    logger.warning("MCP: radar unavailable (%s) — using bundled mock", exc)


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
# Date extraction and deadline determination
# --------------------------------------------------------------------------- #
_DEFAULT_DEADLINES = {
    "Battery": "2027-02-18",
    "RoHS": "2027-07-22",
    "REACH": "2026-10-30",
    "WEEE": "2027-08-18",
    "EMC": "2027-09-01",
    "LVD": "2027-09-01",
    "RED": "2027-08-18",
    "ToySafety": "2027-01-20",
    "GPSR": "2026-12-13",
    "EnergyLabel": "2027-03-01",
    "ESPR": "2027-06-20",
    "PPWR": "2027-08-18",
    "POPs": "2026-10-01",
    "MDR": "2027-05-01",
    "Machinery": "2027-08-18",
}

def _parse_date_str(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %Y", "%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None

def _determine_deadline(reg: dict, key_dates: list[str]) -> str | None:
    # 1. Try deadline_date from regulation dict
    d = reg.get("deadline_date")
    if d:
        return d
    
    # 2. Try extracting from key_dates (prefer dates >= 2024)
    parsed_dates = []
    for s in key_dates:
        parsed = _parse_date_str(s)
        if parsed and parsed.year >= 2024:
            parsed_dates.append(parsed)
        else:
            m = re.search(r'\b\d{4}\b', s)
            if m:
                try:
                    yr = int(m.group(0))
                    if yr >= 2024:
                        parsed_dates.append(date(yr, 12, 31))
                except Exception:
                    pass
    if parsed_dates:
        return min(parsed_dates).strftime("%Y-%m-%d")
        
    # 3. Try fallback to category mapping
    label = reg.get("regulation_family", "")
    return _DEFAULT_DEADLINES.get(label, "2027-02-18")


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

    # 1) Sequentially build the candidate set (scope check, dedupe, RAG retrieval).
    #    DB + ChromaDB stay single-threaded here.
    candidates: list[tuple[models.Product, list[str], str]] = []
    for product in targets:
        applies, reason = _applies(product, reg)
        if not applies:
            logger.info("SKIP %s vs %s: %s", product.name, label, reason)
            continue
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
        candidates.append((product, lines, reason))

    # 2) Evaluate gaps in parallel (LLM calls only — no DB/Chroma in threads).
    def _eval(item: tuple[models.Product, list[str], str]) -> tuple:
        product, lines, reason = item
        try:
            verdict = _evaluate_gap(product, reg, lines, reason)
        except Exception as exc:  # noqa: BLE001
            logger.warning("gap eval failed for %s/%s: %s", product.name, label, exc)
            verdict = None
        return product, lines, verdict

    results = []
    if candidates:
        with ThreadPoolExecutor(max_workers=_GAP_WORKERS) as pool:
            results = list(pool.map(_eval, candidates))

    # 3) Sequentially persist alerts for confirmed gaps.
    created = 0
    for product, lines, verdict in results:
        if not verdict or not verdict.get("has_gap"):
            continue
        company = product.user.company_name if product.user else ""
        message = _build_message(product, company, reg, verdict["gap"])
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
            deadline=_determine_deadline(reg, key_dates),
            source_url=source_url,
            confidence=verdict.get("confidence", 80),
            alert_message=message,
            citations=citations,
            product_impact=verdict.get("product_impact") or impact_svc.product_impact(label, product),
            business_impact=verdict.get("business_impact") or impact_svc.business_impact(reg.get("severity", "medium")),
            key_dates=key_dates,
        )
        # Don't mass-blast during a scan: alerts start "pending" and are sent
        # explicitly (per-alert) unless ALERT_AUTOSEND is on.
        if settings.ALERT_AUTOSEND:
            result = alert_sender.send_alert(
                to="", body=message, channel="sms",
                product=product.name, product_id=product.id,
            )
            alert.delivery_status = result["status"]
        else:
            alert.delivery_status = "pending"
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
