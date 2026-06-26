"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
class UserBase(BaseModel):
    email: EmailStr
    company_name: str


class UserCreate(UserBase):
    pass


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    partner_id: str | None = None


class LoginRequest(BaseModel):
    partner_id: str


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #
class ProductBase(BaseModel):
    name: str
    description: str = ""
    category: str = ""
    substances: list[str] = Field(default_factory=list)
    markets: list[str] = Field(default_factory=list)
    compliance_streams: list[str] = Field(default_factory=list)
    has_battery: bool = False
    battery_type: str = "none"
    battery_capacity_wh: float = 0.0
    has_radio: bool = False
    intended_use: str = "consumer"
    packaging: list[str] = Field(default_factory=list)


class ProductCreate(ProductBase):
    user_id: str | None = None  # falls back to the demo user if omitted


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    substances: list[str] | None = None
    markets: list[str] | None = None
    compliance_streams: list[str] | None = None
    has_battery: bool | None = None
    battery_type: str | None = None
    battery_capacity_wh: float | None = None
    has_radio: bool | None = None
    intended_use: str | None = None
    packaging: list[str] | None = None


class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    created_at: datetime
    open_alerts: int = 0


# --------------------------------------------------------------------------- #
# Classification (Workflow A)
# --------------------------------------------------------------------------- #
class ClassifyRequest(BaseModel):
    description: str = Field(..., min_length=3)
    name: str | None = None


class ClassifyResult(BaseModel):
    """The AI's draft prediction — the UI populates an editable form with this."""
    name: str = ""
    category: str = ""
    substances: list[str] = Field(default_factory=list)
    has_battery: bool = False
    battery_type: str = "none"
    battery_capacity_wh: float = 0.0
    has_radio: bool = False
    intended_use: str = "consumer"
    markets: list[str] = Field(default_factory=list)
    compliance_streams: list[str] = Field(default_factory=list)
    reasoning: str = ""


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #
class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_id: str
    regulation_label: str
    regulation_title: str
    alert_message: str
    requirement: str
    gap: str
    recommended_action: str
    severity: str
    deadline: str | None
    source_url: str
    confidence: int
    delivery_status: str
    citations: list[dict] = Field(default_factory=list)
    product_impact: str = ""
    business_impact: str = ""
    key_dates: list[str] = Field(default_factory=list)
    is_read: bool
    created_at: datetime
    # convenience joins
    product_name: str | None = None
    company_name: str | None = None


# --------------------------------------------------------------------------- #
# Dashboard / misc
# --------------------------------------------------------------------------- #
class DashboardMetrics(BaseModel):
    total_products: int
    active_alerts: int
    monitored_regulations: int


class ScanResult(BaseModel):
    updated_labels: list[str]
    products_assessed: int
    alerts_created: int
    message: str
