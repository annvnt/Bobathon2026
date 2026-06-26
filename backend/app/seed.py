"""Seed the relational DB from the bundled SME portfolio (partners.json).

Each partner becomes a User (the SME company); each of its products becomes a
Product row. Idempotent: skips seeding if users already exist.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .config import settings

logger = logging.getLogger("ecocomply.seed")

# A single "demo" SME used for products added via the UI when no company is set.
DEMO_EMAIL = "demo@ecocomply.example.com"
DEMO_COMPANY = "Demo Electronics GmbH"


def _synth_description(p: dict) -> str:
    bits = [f"{p.get('name')} — {p.get('category', '').replace('_', ' ')}."]
    if p.get("has_battery"):
        bits.append(
            f"Contains a {p.get('battery_type', 'portable')} battery "
            f"({p.get('battery_capacity_wh', 0)} Wh, "
            f"{p.get('battery_chemistry') or 'unspecified'} chemistry)."
        )
    if p.get("has_radio"):
        bits.append("Includes a wireless radio module.")
    if p.get("substances"):
        bits.append("Materials of concern: " + ", ".join(p["substances"]) + ".")
    bits.append(f"Intended use: {p.get('intended_use', 'consumer')}.")
    bits.append("Sold in: " + ", ".join(p.get("markets", [])) + ".")
    return " ".join(bits)


def ensure_demo_user(db: Session) -> models.User:
    user = db.execute(
        select(models.User).where(models.User.email == DEMO_EMAIL)
    ).scalars().first()
    if not user:
        user = models.User(email=DEMO_EMAIL, company_name=DEMO_COMPANY, partner_id="DEMO")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def seed_from_partners(db: Session, force: bool = False) -> int:
    count = db.execute(select(func.count(models.User.id))).scalar() or 0
    if count > 0 and not force:
        logger.info("DB already has %d users — skipping seed.", count)
        return 0

    path = settings.dataset_dir / "partners.json"
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Could not load partners.json: %s", exc)
        ensure_demo_user(db)
        return 0

    partners = data.get("partners", [])
    n_products = 0
    for partner in partners:
        contact = partner.get("contact", {})
        user = models.User(
            email=contact.get("email", f"{partner['partner_id']}@example.com"),
            company_name=partner.get("company", partner["partner_id"]),
            partner_id=partner.get("partner_id"),
        )
        db.add(user)
        db.flush()  # get user.id

        for prod in partner.get("products", []):
            db.add(models.Product(
                user_id=user.id,
                name=prod.get("name", ""),
                description=_synth_description(prod),
                category=prod.get("category", ""),
                substances=prod.get("substances", []) or [],
                markets=prod.get("markets", []) or [],
                compliance_streams=prod.get("compliance_streams", []) or [],
                has_battery=bool(prod.get("has_battery", False)),
                battery_type=prod.get("battery_type", "none") or "none",
                battery_capacity_wh=float(prod.get("battery_capacity_wh", 0) or 0),
                has_radio=bool(prod.get("has_radio", False)),
                intended_use=prod.get("intended_use", "consumer") or "consumer",
                packaging=prod.get("packaging", []) or [],
                source_partner_id=partner.get("partner_id"),
                source_product_id=prod.get("product_id"),
            ))
            n_products += 1

    ensure_demo_user(db)
    db.commit()
    logger.info("Seeded %d partners / %d products.", len(partners), n_products)
    return n_products
