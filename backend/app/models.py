"""SQLAlchemy ORM models for the relational store (Users, Products, Alerts)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    partner_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)

    products: Mapped[list["Product"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="", index=True)

    # JSON arrays — portable across SQLite/Postgres via SQLAlchemy JSON type.
    substances: Mapped[list] = mapped_column(JSON, default=list)
    markets: Mapped[list] = mapped_column(JSON, default=list)
    compliance_streams: Mapped[list] = mapped_column(JSON, default=list)

    has_battery: Mapped[bool] = mapped_column(Boolean, default=False)

    # Extra attributes from the portfolio dataset — drive precise gap reasoning.
    battery_type: Mapped[str] = mapped_column(String(32), default="none")
    battery_capacity_wh: Mapped[float] = mapped_column(Float, default=0.0)
    has_radio: Mapped[bool] = mapped_column(Boolean, default=False)
    intended_use: Mapped[str] = mapped_column(String(32), default="consumer")
    packaging: Mapped[list] = mapped_column(JSON, default=list)

    # Traceability back to the source dataset (optional).
    source_partner_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_product_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship(back_populates="products")
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)

    regulation_label: Mapped[str] = mapped_column(String(64), index=True)
    alert_message: Mapped[str] = mapped_column(Text)

    # Richer finding fields (match sample_expected_output.json shape).
    regulation_title: Mapped[str] = mapped_column(String(512), default="")
    requirement: Mapped[str] = mapped_column(Text, default="")
    gap: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    deadline: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    confidence: Mapped[int] = mapped_column(Integer, default=80)
    delivery_status: Mapped[str] = mapped_column(String(32), default="pending")

    # Line-by-line citations from the regulation text stored in the vector DB,
    # each with cause/effect + product & business impact + extracted dates.
    citations: Mapped[list] = mapped_column(JSON, default=list)
    product_impact: Mapped[str] = mapped_column(Text, default="")
    business_impact: Mapped[str] = mapped_column(Text, default="")
    key_dates: Mapped[list] = mapped_column(JSON, default=list)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    product: Mapped["Product"] = relationship(back_populates="alerts")
