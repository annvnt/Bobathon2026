"""Portfolio analytics — aggregates, risk/health/exposure orbs, deadline timeline."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import label_map, models

# Estimated fine exposure per open gap, by severity (illustrative).
_FINE = {"high": 100_000, "medium": 20_000, "low": 2_000}
_SEV_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %Y", "%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def compute_product_analytics(db: Session, product_id: str) -> dict | None:
    product = db.get(models.Product, product_id)
    if not product:
        return None

    alerts = db.execute(
        select(models.Alert).where(models.Alert.product_id == product_id)
    ).scalars().all()
    open_alerts = [a for a in alerts if not a.is_read]

    by_severity = Counter(a.severity for a in open_alerts)
    by_label = Counter(a.regulation_label for a in open_alerts)

    risk = min(
        100,
        by_severity.get("high", 0) * 45
        + by_severity.get("medium", 0) * 25
        + by_severity.get("low", 0) * 10,
    )
    fine = sum(_FINE.get(a.severity, 0) for a in open_alerts)

    today = datetime.now(timezone.utc).date()
    timeline = []
    for a in open_alerts:
        d = _parse_date(a.deadline)
        timeline.append({
            "alert_id": a.id,
            "deadline": a.deadline,
            "days_remaining": (d - today).days if d else None,
            "label": a.regulation_label,
            "severity": a.severity,
            "title": a.regulation_title,
        })
    timeline.sort(key=lambda t: (t["days_remaining"] is None, t["days_remaining"] if t["days_remaining"] is not None else 1e9))

    gaps_by_label = dict(by_label)
    coverage = []
    for lab in (product.compliance_streams or []):
        ld = label_map.get(lab)
        coverage.append({
            "label": lab,
            "regulation": ld.regulation if ld else lab,
            "source_url": ld.source_url if ld else "",
            "open_gaps": gaps_by_label.get(lab, 0),
        })
    coverage.sort(key=lambda c: c["open_gaps"], reverse=True)

    return {
        "product": {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "description": product.description,
            "substances": product.substances or [],
            "markets": product.markets or [],
            "compliance_streams": product.compliance_streams or [],
            "has_battery": product.has_battery,
            "battery_type": product.battery_type,
            "battery_capacity_wh": product.battery_capacity_wh,
            "has_radio": product.has_radio,
            "intended_use": product.intended_use,
        },
        "company": product.user.company_name if product.user else "",
        "totals": {
            "open_alerts": len(open_alerts),
            "total_alerts": len(alerts),
            "labels_in_scope": len(product.compliance_streams or []),
            "labels_with_gaps": len([c for c in coverage if c["open_gaps"] > 0]),
        },
        "orbs": {
            "risk": risk,
            "health": 100 - risk,
            "fine_exposure_eur": fine,
        },
        "by_severity": {k: by_severity.get(k, 0) for k in ("high", "medium", "low")},
        "by_label": dict(by_label),
        "coverage": coverage,
        "timeline": timeline,
    }


def compute_analytics(db: Session, user_id: str | None = None) -> dict:
    prod_stmt = select(models.Product)
    if user_id:
        prod_stmt = prod_stmt.where(models.Product.user_id == user_id)
    products = db.execute(prod_stmt).scalars().all()
    product_ids = {p.id for p in products}

    alerts = db.execute(select(models.Alert)).scalars().all()
    alerts = [a for a in alerts if a.product_id in product_ids]
    open_alerts = [a for a in alerts if not a.is_read]

    # ---- distributions ----
    by_severity = Counter(a.severity for a in open_alerts)
    by_label = Counter(a.regulation_label for a in open_alerts)
    products_by_id = {p.id: p for p in products}
    by_category = Counter(
        products_by_id[a.product_id].category for a in open_alerts if a.product_id in products_by_id
    )
    products_by_category = Counter(p.category for p in products)

    n_products = len(products)
    flagged_products = {a.product_id for a in open_alerts}
    n_clean = n_products - len(flagged_products)

    # ---- orbs ----
    weighted = sum(_SEV_WEIGHT.get(a.severity, 1) for a in open_alerts)
    risk = min(100, round(100 * weighted / max(1, n_products * 3)))
    health = 100 - risk
    fine_exposure = sum(_FINE.get(a.severity, 0) for a in open_alerts)

    # ---- deadline timeline ----
    today = datetime.now(timezone.utc).date()
    timeline = []
    soon = 0
    for a in open_alerts:
        d = _parse_date(a.deadline)
        days = (d - today).days if d else None
        if days is not None and days <= 365:
            soon += 1
        timeline.append({
            "alert_id": a.id,
            "deadline": a.deadline,
            "days_remaining": days,
            "label": a.regulation_label,
            "severity": a.severity,
            "product": products_by_id.get(a.product_id).name if a.product_id in products_by_id else "",
            "company": (
                products_by_id[a.product_id].user.company_name
                if a.product_id in products_by_id and products_by_id[a.product_id].user
                else ""
            ),
        })
    timeline.sort(key=lambda t: (t["days_remaining"] is None, t["days_remaining"] if t["days_remaining"] is not None else 1e9))
    deadline_pressure = min(100, round(100 * soon / max(1, len(open_alerts)))) if open_alerts else 0

    # ---- per-company risk ----
    companies: dict[str, dict] = {}
    for p in products:
        if not p.user:
            continue
        c = companies.setdefault(p.user.id, {
            "company": p.user.company_name,
            "partner_id": p.user.partner_id,
            "products": 0, "high": 0, "medium": 0, "low": 0, "open_alerts": 0,
        })
        c["products"] += 1
    for a in open_alerts:
        p = products_by_id.get(a.product_id)
        if not p or not p.user:
            continue
        c = companies[p.user.id]
        c["open_alerts"] += 1
        c[a.severity] = c.get(a.severity, 0) + 1
    company_risk = []
    for c in companies.values():
        w = c["high"] * 3 + c["medium"] * 2 + c["low"] * 1
        c["risk"] = min(100, round(100 * w / max(1, c["products"] * 3)))
        company_risk.append(c)
    company_risk.sort(key=lambda c: c["risk"], reverse=True)

    # ---- label coverage (monitored vs triggered) ----
    label_coverage = []
    for ld in label_map.load_labels().values():
        triggered = sum(1 for p in products if ld.label in (p.compliance_streams or []))
        gaps = by_label.get(ld.label, 0)
        label_coverage.append({
            "label": ld.label,
            "regulation": ld.regulation,
            "source_url": ld.source_url,
            "products_in_scope": triggered,
            "open_gaps": gaps,
        })
    label_coverage.sort(key=lambda x: x["open_gaps"], reverse=True)

    return {
        "totals": {
            "products": n_products,
            "companies": len(companies) if not user_id else 1,
            "open_alerts": len(open_alerts),
            "clean_products": n_clean,
            "flagged_products": len(flagged_products),
        },
        "orbs": {
            "portfolio_risk": risk,
            "compliance_health": health,
            "fine_exposure_eur": fine_exposure,
            "deadline_pressure": deadline_pressure,
        },
        "by_severity": {k: by_severity.get(k, 0) for k in ("high", "medium", "low")},
        "by_label": dict(by_label),
        "by_category": dict(by_category),
        "products_by_category": dict(products_by_category),
        "timeline": timeline[:20],
        "company_risk": company_risk[:15],
        "label_coverage": label_coverage,
    }
