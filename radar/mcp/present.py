"""Presentation flow — AI structured request → applicable regulations for display."""

from __future__ import annotations

import json
from typing import Any

from radar.compliance import taxonomy
from radar.config import PARTNERS_FILE
from radar.mcp.regulation_ops import fetch_regulation
from radar.mcp import label_regs

EXCERPT_LEN = 480


def _load_partners() -> list[dict[str, Any]]:
    if not PARTNERS_FILE.exists():
        return []
    data = json.loads(PARTNERS_FILE.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for partner in data.get("partners", []):
        for product in partner.get("products", []):
            out.append({
                **product,
                "partner_id": partner.get("partner_id"),
                "company": partner.get("name"),
            })
    return out


def find_product(product_id: str) -> dict[str, Any] | None:
    pid = product_id.strip()
    for product in _load_partners():
        if product.get("product_id") == pid:
            return product
    return None


def list_products() -> list[dict[str, Any]]:
    """Lightweight catalog for presentation UI."""
    items: list[dict[str, Any]] = []
    for product in _load_partners():
        items.append({
            "product_id": product.get("product_id"),
            "name": product.get("name"),
            "company": product.get("company"),
            "category": product.get("category"),
            "markets": product.get("markets", []),
            "compliance_streams": product.get("compliance_streams", []),
        })
    return sorted(items, key=lambda p: p.get("product_id") or "")


def infer_labels(product: dict[str, Any] | None, labels: list[str] | None) -> list[str]:
    if labels:
        return sorted({l.strip() for l in labels if l and l.strip()})
    if not product:
        return []
    streams = product.get("compliance_streams") or []
    if streams:
        return sorted({s.strip() for s in streams if s and s.strip()})
    inferred: set[str] = set()
    blob = " ".join(
        filter(
            None,
            [
                product.get("name"),
                product.get("category"),
                product.get("battery_type"),
                product.get("intended_use"),
            ],
        )
    )
    family = taxonomy.detect_family(blob)
    if family:
        inferred.add(family)
    if product.get("has_battery"):
        inferred.add("Battery")
    if product.get("has_radio"):
        inferred.add("RED")
    substances = product.get("substances") or []
    if substances:
        inferred.update({"REACH", "RoHS"})
    return sorted(inferred)


def infer_countries(product: dict[str, Any] | None, countries: list[str] | None) -> list[str]:
    if countries:
        return sorted({c.strip().upper() for c in countries if c and c.strip()})
    if not product:
        return ["EU"]
    markets = product.get("markets") or []
    if not markets:
        return ["EU"]
    return sorted({m.strip().upper() for m in markets if m and m.strip()})


def _reg_id(record: dict[str, Any]) -> str:
    category = record.get("category") or "unknown"
    country = record.get("country") or "XX"
    reference = record.get("reference") or "ref"
    return f"{category}__{country}__{reference}"


def to_display_record(record: dict[str, Any]) -> dict[str, Any]:
    text = record.get("text") or ""
    return {
        "id": _reg_id(record),
        "source": record.get("label") or "",
        "family": record.get("category") or "",
        "country": record.get("country") or "",
        "countries_affected": record.get("countries_affected") or [],
        "title": record.get("title") or record.get("reference") or "",
        "reference": record.get("reference") or "",
        "url": record.get("source_url") or "",
        "gadi_url": record.get("gadi_url") or "",
        "excerpt": text[:EXCERPT_LEN] + ("…" if len(text) > EXCERPT_LEN else ""),
        "regulation_text_preview": text[:12000] if text else "",
        "text_chars": len(text),
        "regulation_text_key": record.get("regulation_text_key"),
        "stored_at": record.get("stored_at"),
        "match_score": 100,
    }


def present_regulations(
    *,
    product_id: str | None = None,
    labels: list[str] | None = None,
    countries: list[str] | None = None,
    save: bool = False,
) -> dict[str, Any]:
    """
    Presentation entry point: structured AI request → regulations ready for UI cards.

    When product_id is set, labels and countries are inferred from the portfolio
    unless explicitly overridden.
    """
    product = find_product(product_id) if product_id else None
    labels_norm = infer_labels(product, labels)
    countries_norm = infer_countries(product, countries)

    if not labels_norm:
        return {
            "error": "no_labels",
            "message": "Provide compliance labels or a known product_id from the portfolio.",
            "product_id": product_id,
        }
    if not countries_norm:
        return {
            "error": "no_countries",
            "message": "Provide delivery countries or a product with markets.",
            "product_id": product_id,
        }

    if save and product_id:
        stored = fetch_regulation(
            labels_norm,
            countries_norm,
            product_id=product_id,
            save=True,
        )
        regulations = stored.get("regulations", [])
    else:
        result = label_regs.regulations_for_labels(
            labels_norm,
            countries_norm,
            fetch_missing=True,
            save=False,
            product_id=product_id,
        )
        regulations = result.get("regulations", [])
        if not regulations:
            result = label_regs.resolve_labels(labels_norm, countries_norm, product_id=product_id)
            regulations = result.get("regulations", [])

    display = [to_display_record(r) for r in regulations]
    product_name = (product or {}).get("name") or ""
    company = (product or {}).get("company") or ""

    message_parts = [
        {
            "type": "text",
            "content": (
                f"Applicable regulations for "
                f"{product_name or 'this product'}"
                f"{f' ({company})' if company else ''}"
                f" — labels: {', '.join(labels_norm)}; markets: {', '.join(countries_norm)}."
            ),
        },
    ]

    return {
        "mode": "ai_present",
        "product_id": product_id,
        "product_name": product_name,
        "company": company,
        "labels": labels_norm,
        "countries": countries_norm,
        "regulations": display,
        "message_parts": message_parts,
        "count": len(display),
        "saved": bool(save and product_id),
    }
