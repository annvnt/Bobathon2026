"""Alert delivery — Twilio when configured, otherwise a logging mock.

Switching is a config change (ALERTS_PROVIDER); callers are unchanged.
"""
from __future__ import annotations

import logging

from ..config import settings

logger = logging.getLogger("ecocomply.alerts")


def _send_twilio(to: str, body: str, channel: str) -> str:
    from twilio.rest import Client  # lazy import; optional dependency

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    from_ = settings.TWILIO_FROM_NUMBER
    if channel == "whatsapp":
        to = f"whatsapp:{to}"
        from_ = f"whatsapp:{from_}"
    msg = client.messages.create(body=body, from_=from_, to=to)
    return msg.sid


def send_alert(*, to: str, body: str, channel: str = "sms") -> dict:
    """Deliver one alert. Returns {status, detail}."""
    # Always route to your own test number if configured, so nothing reaches a
    # real contact (portfolio data is synthetic anyway).
    target = settings.TWILIO_TEST_TO_NUMBER or to

    if settings.ALERTS_PROVIDER == "twilio" and settings.TWILIO_ACCOUNT_SID:
        try:
            sid = _send_twilio(target, body, channel)
            return {"status": "delivered", "detail": sid}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Twilio send failed: %s", exc)
            return {"status": "failed", "detail": str(exc)}

    # Mock: log it. Counts as "delivered" for demo flow.
    logger.info("[MOCK ALERT → %s via %s]\n%s", target, channel, body)
    return {"status": "delivered", "detail": "mock"}
