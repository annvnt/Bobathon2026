"""Alert delivery — connected to the team sender `radar.alerts.notify`.

`radar.alerts.notify.send_alert(gap)` sends via Twilio (SMS / WhatsApp) or writes
an email stub, reading credentials from the repo-root `.env`. It honours
`ALERT_TO_OVERRIDE` to route every message to one verified test recipient.

Falls back to a logging mock if radar can't be imported or ALERTS_PROVIDER=mock.
"""
from __future__ import annotations

import logging
import sys

from ..config import REPO_ROOT, settings

logger = logging.getLogger("ecocomply.alerts")

# Make the repo-root `radar` package importable from the backend.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from radar.alerts import notify as _radar_notify
except Exception as exc:  # noqa: BLE001
    _radar_notify = None
    logger.warning("radar.alerts.notify unavailable (%s) — alert sending will mock", exc)


def send_alert(
    *,
    to: str,
    body: str,
    channel: str = "sms",
    product: str = "",
    product_id: str = "",
) -> dict:
    """Deliver one alert. Returns {status, detail}."""
    recipient = to or settings.ALERT_TO_OVERRIDE

    if settings.ALERTS_PROVIDER == "twilio" and _radar_notify is not None:
        gap = {
            "product": product,
            "product_id": product_id or "alert",
            "alert": {"channel": channel, "to": recipient, "message": body},
        }
        try:
            r = _radar_notify.send_alert(gap)
        except Exception as exc:  # noqa: BLE001
            logger.warning("radar notify failed: %s", exc)
            return {"status": "failed", "detail": str(exc)}
        status = r.get("status", "unknown")
        mapped = {
            "sent": "delivered",
            "email_stub": "delivered",
            "dry_run": "pending",
            "skipped": "skipped",
        }.get(status, status)
        return {"status": mapped, "detail": r.get("sid") or r.get("path") or r.get("reason") or status}

    # Mock: log only.
    logger.info("[MOCK ALERT → %s via %s]\n%s", recipient or "(no recipient)", channel, body)
    return {"status": "logged", "detail": "mock"}
