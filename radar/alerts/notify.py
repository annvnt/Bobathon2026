"""Twilio alert dispatch."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from radar.compliance import findings
from radar.config import GAPS_FILE, OPTOUTS_FILE, OUTPUT, ensure_dirs, env, load_dotenv

MAX_CONCURRENT = 5
RETRY_BACKOFF = 5


def _load_optouts() -> set[str]:
    if not OPTOUTS_FILE.exists():
        return set()
    data = json.loads(OPTOUTS_FILE.read_text(encoding="utf-8"))
    return set(data if isinstance(data, list) else [])


def _normalize_phone(phone: str) -> str:
    return "".join(c for c in phone if c.isdigit() or c == "+")


def _twilio_post(account_sid: str, auth_token: str, payload: dict) -> dict:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    body = urllib.parse.urlencode(payload).encode("utf-8")
    cred = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Basic {cred}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(RETRY_BACKOFF)
                continue
            raise
    return {}


def send_alert(gap: dict, dry_run: bool = False) -> dict:
    load_dotenv()
    override = env("ALERT_TO_OVERRIDE")
    optouts = _load_optouts()
    alert = gap.get("alert", {})
    channel = alert.get("channel", "sms")
    to = override or alert.get("to", "")
    message = alert.get("message", "")

    if not to:
        return {"status": "skipped", "reason": "no recipient"}
    if _normalize_phone(to) in optouts:
        return {"status": "skipped", "reason": "opted out"}

    account_sid = env("TWILIO_ACCOUNT_SID")
    auth_token = env("TWILIO_AUTH_TOKEN")
    from_number = env("TWILIO_FROM_NUMBER")

    if channel == "email":
        eml_path = OUTPUT / "alerts" / f"{gap.get('product_id', 'alert')}.eml"
        eml_path.parent.mkdir(parents=True, exist_ok=True)
        eml_path.write_text(
            f"To: {to}\nSubject: Regulatory gap — {gap.get('product')}\n\n{message}\n\n{gap.get('gap')}\n",
            encoding="utf-8",
        )
        print(f"Email stub written: {eml_path}")
        return {"status": "email_stub", "path": str(eml_path)}

    if not account_sid or not auth_token or not from_number:
        print(f"[dry] Would send {channel} to {to}: {message[:80]}...")
        return {"status": "dry_run", "channel": channel, "to": to}

    payload = {"To": to, "From": from_number, "Body": message}
    if channel == "whatsapp":
        payload["To"] = f"whatsapp:{_normalize_phone(to)}"
        payload["From"] = f"whatsapp:{from_number}"

    if dry_run:
        return {"status": "dry_run", "payload": payload}

    result = _twilio_post(account_sid, auth_token, payload)
    return {"status": "sent", "sid": result.get("sid")}


def alert_all(dry_run: bool = False) -> list[dict]:
    ensure_dirs()
    load_dotenv()
    if not GAPS_FILE.exists():
        print("No gaps file - run evaluate first")
        return []
    gaps = json.loads(GAPS_FILE.read_text(encoding="utf-8"))
    results = []
    for gap in gaps[:MAX_CONCURRENT * 10]:
        if gap.get("status") == "in_review":
            print(f"  {gap.get('product_id')}: skipped (in_review — admin approval required)")
            results.append({"status": "skipped", "reason": "in_review", "product_id": gap.get("product_id")})
            continue
        try:
            r = send_alert(gap, dry_run=dry_run)
            findings.log_alert(gap, r)
            results.append({**r, "product_id": gap.get("product_id")})
            print(f"  {gap.get('product_id')}: {r.get('status')}")
        except Exception as e:
            print(f"  {gap.get('product_id')}: error - {e}")
            results.append({"status": "error", "error": str(e)})
    return results
