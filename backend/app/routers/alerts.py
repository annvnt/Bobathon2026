"""Alerts — list, get, mark read."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..schemas import AlertOut
from ..services import alerts as alert_sender

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _to_out(alert: models.Alert) -> AlertOut:
    out = AlertOut.model_validate(alert)
    if alert.product:
        out.product_name = alert.product.name
        if alert.product.user:
            out.company_name = alert.product.user.company_name
    return out


@router.get("", response_model=list[AlertOut])
def list_alerts(
    is_read: bool | None = None,
    product_id: str | None = None,
    user_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[AlertOut]:
    stmt = select(models.Alert).join(models.Product)
    if is_read is not None:
        stmt = stmt.where(models.Alert.is_read == is_read)
    if product_id:
        stmt = stmt.where(models.Alert.product_id == product_id)
    if user_id:
        stmt = stmt.where(models.Product.user_id == user_id)
    alerts = db.execute(stmt.order_by(models.Alert.created_at.desc())).scalars().all()
    return [_to_out(a) for a in alerts]


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: str, db: Session = Depends(get_db)) -> AlertOut:
    alert = db.get(models.Alert, alert_id)
    if not alert:
        raise HTTPException(404, "alert not found")
    return _to_out(alert)


@router.post("/{alert_id}/read", response_model=AlertOut)
def mark_read(alert_id: str, db: Session = Depends(get_db)) -> AlertOut:
    alert = db.get(models.Alert, alert_id)
    if not alert:
        raise HTTPException(404, "alert not found")
    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return _to_out(alert)


@router.post("/{alert_id}/send", response_model=AlertOut)
def send_alert(
    alert_id: str,
    to: str | None = None,
    channel: str = "sms",
    db: Session = Depends(get_db),
) -> AlertOut:
    """Fire this alert as a real message (Twilio SMS/WhatsApp via radar.alerts.notify).

    Routes to `to` if given, else the configured ALERT_TO_OVERRIDE test recipient.
    """
    alert = db.get(models.Alert, alert_id)
    if not alert:
        raise HTTPException(404, "alert not found")
    product = alert.product
    result = alert_sender.send_alert(
        to=to or "",
        body=alert.alert_message,
        channel=channel,
        product=product.name if product else "",
        product_id=product.id if product else "",
    )
    alert.delivery_status = result["status"]
    db.commit()
    db.refresh(alert)
    return _to_out(alert)
