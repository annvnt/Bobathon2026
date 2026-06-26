#!/usr/bin/env python3
"""
send_compliance_alerts.py

Reads compliance-gap "findings" (in the JSON shape your agent emits) and
sends the embedded alert via SMS, WhatsApp, or email -- routed by the
finding's `alert.channel` field.

============================================================
SECURITY NOTE -- credentials
============================================================
All credentials are read from environment variables, never hard-coded.
Any credential value that has ever been typed into a chat, ticket, or
shared document should be treated as compromised -- rotate it in the
relevant console before relying on this script.

------------------------------------------------------------
SMS / WhatsApp -- Twilio
------------------------------------------------------------
You need your Account SID (starts with "AC...", on your Twilio Console
dashboard) plus ONE of:

  Option A - Main Auth Token (simplest):
      TWILIO_ACCOUNT_SID="AC..."
      TWILIO_AUTH_TOKEN="your_auth_token"

  Option B - Scoped API Key (recommended for least-privilege/agents):
      TWILIO_ACCOUNT_SID="AC..."
      TWILIO_API_KEY_SID="SK..."
      TWILIO_API_KEY_SECRET="your_api_key_secret"

Note: an API Key SID ("SK...") is NOT the same as your Account SID
("AC..."). Twilio API URLs are always scoped under /Accounts/{AccountSid}/,
so the Account SID must always be set, even when authenticating with an
API Key.

For SMS, also set:
      TWILIO_FROM_NUMBER="+1xxxxxxxxxx"     # your Twilio-purchased number

For WhatsApp, also set:
      TWILIO_WHATSAPP_FROM="whatsapp:+14155238886"

  -- Using the Twilio Sandbox for testing (your case): the sandbox number
     is almost always "whatsapp:+14155238886", but confirm yours at
     Console -> Messaging -> Try it out -> Send a WhatsApp message.
     IMPORTANT one-time step: every "to" number must first send the
     sandbox's join code (e.g. "join some-word") to that sandbox number
     from WhatsApp on the actual phone, or Twilio will reject the send.
     This expires periodically and needs to be redone.

  -- WhatsApp Content Templates: outside the 24-hour customer-service
     session window (i.e. you're messaging first, business-initiated),
     WhatsApp requires an approved template instead of free-form text.
     A finding's alert object can specify this instead of (or alongside)
     "message":
         "alert": {
           "channel": "whatsapp",
           "to": "+491639264879",
           "content_sid": "HXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
           "content_variables": {"1": "12/1", "2": "3pm"}
         }
     content_variables may be a dict (it'll be JSON-encoded automatically)
     or a pre-encoded JSON string. Find content_sid values under
     Console -> Messaging -> Content Template Builder.

------------------------------------------------------------
Email -- SendGrid (optional)
------------------------------------------------------------
Email support is optional. If you haven't set up SendGrid yet, just don't
set these variables -- the script works fine with SMS/WhatsApp only, and
any email-channel findings will be cleanly skipped (not crash the batch).

When you're ready:
  1. Sign up at https://sendgrid.com and create an API key
     (Settings -> API Keys -> Create API Key -> "Mail Send" permission).
  2. Verify a sender identity or domain (Settings -> Sender Authentication)
     -- SendGrid will not send "from" an unverified address.
  3. Set:
      SENDGRID_API_KEY="SG...."
      SENDGRID_FROM_EMAIL="alerts@yourdomain.com"   # must be verified
      SENDGRID_DATA_RESIDENCY="eu"    # optional; "eu" or "global" (default)

  EU data residency routes the request through SendGrid's EU infrastructure
  instead of the global default -- relevant if you or your recipients are
  EU-based and want data handled there. Leave SENDGRID_DATA_RESIDENCY unset
  for the global default.

  IMPORTANT: never put your API key directly in a script or commit it to
  git. A `sendgrid.env` file works well as long as it's listed in
  .gitignore and only ever loaded locally, e.g.:
      echo "export SENDGRID_API_KEY='SG.xxxx'" > sendgrid.env
      echo "export SENDGRID_FROM_EMAIL='alerts@yourdomain.com'" >> sendgrid.env
      echo "sendgrid.env" >> .gitignore
      source ./sendgrid.env
  (PowerShell equivalent: put $env:SENDGRID_API_KEY = "..." lines in a
  .ps1 file, add it to .gitignore, and dot-source it: . ./sendgrid.ps1)

------------------------------------------------------------
Setting environment variables
------------------------------------------------------------
PowerShell (Windows), per session:
    $env:TWILIO_ACCOUNT_SID = "AC..."
    $env:TWILIO_API_KEY_SID = "SK..."
    $env:TWILIO_API_KEY_SECRET = "..."
    $env:TWILIO_FROM_NUMBER = "+1..."
    $env:TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"

bash/zsh (macOS/Linux), per session:
    export TWILIO_ACCOUNT_SID="AC..."
    export TWILIO_API_KEY_SID="SK..."
    export TWILIO_API_KEY_SECRET="..."
    export TWILIO_FROM_NUMBER="+1..."
    export TWILIO_WHATSAPP_FROM="whatsapp:+14155238886"

Or put them in a local `.env` file (add `.env` to .gitignore) and load with
`python-dotenv`:
    pip install python-dotenv --break-system-packages
    # then at the top of this script: from dotenv import load_dotenv; load_dotenv()
"""

import os
import sys
import json
import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("compliance_alerts")

SUPPORTED_CHANNELS = ("sms", "whatsapp", "email")


# ============================================================
# Configuration
# ============================================================

@dataclass
class TwilioConfig:
    """Covers SMS and WhatsApp, both sent through the Twilio Messages API."""

    account_sid: str
    auth_token: Optional[str] = None
    api_key_sid: Optional[str] = None
    api_key_secret: Optional[str] = None
    from_number: Optional[str] = None       # for SMS, e.g. "+15551234567"
    whatsapp_from: Optional[str] = None     # e.g. "whatsapp:+14155238886"

    @classmethod
    def from_env(cls) -> Optional["TwilioConfig"]:
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        if not account_sid:
            return None  # Twilio not configured at all

        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        api_key_sid = os.environ.get("TWILIO_API_KEY_SID")
        api_key_secret = os.environ.get("TWILIO_API_KEY_SECRET")

        if not auth_token and not (api_key_sid and api_key_secret):
            raise RuntimeError(
                "TWILIO_ACCOUNT_SID is set but no credentials were given. "
                "Set TWILIO_AUTH_TOKEN, or both TWILIO_API_KEY_SID and "
                "TWILIO_API_KEY_SECRET."
            )

        if not account_sid.startswith("AC"):
            log.warning(
                "TWILIO_ACCOUNT_SID does not start with 'AC' -- you may have "
                "put an API Key SID (starts with 'SK') here by mistake. "
                "Find your real Account SID on the Twilio Console dashboard."
            )
        if api_key_sid and not api_key_sid.startswith("SK"):
            log.warning("TWILIO_API_KEY_SID does not start with 'SK' -- double check it.")

        return cls(
            account_sid=account_sid,
            auth_token=auth_token,
            api_key_sid=api_key_sid,
            api_key_secret=api_key_secret,
            from_number=os.environ.get("TWILIO_FROM_NUMBER"),
            whatsapp_from=os.environ.get("TWILIO_WHATSAPP_FROM"),
        )

    def make_client(self) -> Client:
        if self.api_key_sid and self.api_key_secret:
            return Client(self.api_key_sid, self.api_key_secret, self.account_sid)
        return Client(self.account_sid, self.auth_token)


@dataclass
class SendGridConfig:
    """Optional. Only needed for the 'email' channel."""

    api_key: str
    from_email: str
    data_residency: Optional[str] = None  # "eu" or None (default/global)

    @classmethod
    def from_env(cls) -> Optional["SendGridConfig"]:
        api_key = os.environ.get("SENDGRID_API_KEY")
        from_email = os.environ.get("SENDGRID_FROM_EMAIL")
        if not api_key or not from_email:
            return None  # email channel simply won't be available

        # Catch a very common cause of mysterious 401s: the env var picked
        # up stray quotes or whitespace when sourced from a shell file
        # (e.g. `export SENDGRID_API_KEY='SG.xxx'` sourced in a shell that
        # didn't strip the quotes the way you expected).
        stripped = api_key.strip().strip("'\"")
        if stripped != api_key:
            log.warning(
                "SENDGRID_API_KEY has leading/trailing whitespace or quote "
                "characters -- using a cleaned-up version. Check how the "
                "env var was set (e.g. sendgrid.env / $env: assignment)."
            )
            api_key = stripped
        if not api_key.startswith("SG."):
            log.warning(
                "SENDGRID_API_KEY does not start with 'SG.' -- this doesn't "
                "look like a valid SendGrid API key. Double check the value."
            )

        data_residency = os.environ.get("SENDGRID_DATA_RESIDENCY")  # e.g. "eu"
        if data_residency:
            data_residency = data_residency.strip().lower()
            if data_residency not in ("eu", "global"):
                log.warning(
                    "SENDGRID_DATA_RESIDENCY=%r is not 'eu' or 'global' -- ignoring.",
                    data_residency,
                )
                data_residency = None
            elif data_residency == "global":
                data_residency = None  # global is the SDK default, nothing to set

        return cls(api_key=api_key, from_email=from_email, data_residency=data_residency)


# ============================================================
# Loading & validating findings
# ============================================================

def load_findings(source: str) -> list[dict]:
    """
    Load one or more findings from a JSON file or a JSON string.
    Accepts either a single finding object or a list of findings.
    """
    if os.path.isfile(source):
        with open(source, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.loads(source)

    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError("Findings JSON must be an object or a list of objects.")


def validate_finding(finding: dict) -> None:
    for key in ["company", "product", "alert"]:
        if key not in finding:
            raise ValueError(f"Finding is missing required field: '{key}'")

    alert = finding["alert"]
    channel = alert.get("channel")

    if channel not in SUPPORTED_CHANNELS:
        raise ValueError(
            f"Unsupported alert channel: {channel!r} (expected one of {SUPPORTED_CHANNELS})"
        )

    if not alert.get("to"):
        raise ValueError("Finding's 'alert' object is missing required field: 'to'")

    # Content can be plain text ('message') or, for WhatsApp only, a Content
    # Template reference ('content_sid' + optional 'content_variables').
    has_message = bool(alert.get("message"))
    has_template = bool(alert.get("content_sid"))

    if channel == "sms" and not has_message:
        raise ValueError("SMS findings need a non-empty 'message'.")
    if channel == "email":
        # Email body is built from the finding's own structured fields
        # (company, product, regulation, gap, etc.) rather than requiring
        # alert.message -- but we need at least *some* of that context to
        # produce a non-empty email.
        has_context = any(
            finding.get(k) for k in ("regulation", "requirement", "gap", "recommended_action")
        )
        if not has_context and not has_message:
            raise ValueError(
                "Email findings need either structured context fields "
                "(regulation/requirement/gap/recommended_action) or a "
                "fallback 'message'."
            )
    if channel == "whatsapp" and not (has_message or has_template):
        raise ValueError(
            "WhatsApp findings need either 'message' (plain text) or "
            "'content_sid' (an approved Content Template)."
        )


# ============================================================
# Channel senders
# ============================================================

def send_sms_or_whatsapp(
    twilio_client: Client, twilio_cfg: TwilioConfig, finding: dict, dry_run: bool
) -> Optional[str]:
    alert = finding["alert"]
    channel = alert["channel"]
    to = alert["to"]

    # Two ways to specify content:
    #   1. Plain free-form text -> alert["message"]
    #   2. An approved WhatsApp Content Template -> alert["content_sid"]
    #      (+ optional alert["content_variables"], a dict or JSON string)
    # Template sending is required for WhatsApp messages sent outside the
    # 24-hour customer-service window (i.e. business-initiated messages),
    # and is also fine to use inside the sandbox.
    content_sid = alert.get("content_sid")
    content_variables = alert.get("content_variables")
    body = alert.get("message")

    if channel == "sms":
        if not twilio_cfg.from_number:
            raise RuntimeError("Channel is 'sms' but TWILIO_FROM_NUMBER is not set.")
        from_ = twilio_cfg.from_number
        if content_sid:
            raise RuntimeError(
                "content_sid is a WhatsApp Content Template feature and isn't "
                "supported for plain SMS. Use 'message' instead, or switch "
                "channel to 'whatsapp'."
            )
    else:  # whatsapp
        if not twilio_cfg.whatsapp_from:
            raise RuntimeError("Channel is 'whatsapp' but TWILIO_WHATSAPP_FROM is not set.")
        from_ = twilio_cfg.whatsapp_from
        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"
        if not from_.startswith("whatsapp:"):
            from_ = f"whatsapp:{from_}"

    if not content_sid and not body:
        raise RuntimeError(
            "Alert needs either 'message' (plain text) or 'content_sid' "
            "(+ optional 'content_variables') for a WhatsApp template."
        )

    log.info(
        "Preparing %s alert for %s / %s -> %s%s",
        channel, finding.get("company"), finding.get("product"), to,
        " (template)" if content_sid else "",
    )

    if dry_run:
        if content_sid:
            log.info(
                "[DRY RUN] Would send template content_sid=%s variables=%s",
                content_sid, content_variables,
            )
        else:
            log.info("[DRY RUN] Would send: %s", body)
        return None

    create_kwargs = {"from_": from_, "to": to}
    if content_sid:
        create_kwargs["content_sid"] = content_sid
        if content_variables is not None:
            # Twilio expects this as a JSON string
            if isinstance(content_variables, (dict, list)):
                create_kwargs["content_variables"] = json.dumps(content_variables)
            else:
                create_kwargs["content_variables"] = content_variables
    else:
        create_kwargs["body"] = body

    message = twilio_client.messages.create(**create_kwargs)
    log.info("Sent. Twilio SID=%s status=%s", message.sid, message.status)
    return message.sid


def build_email_body(finding: dict) -> str:
    """
    Builds a readable, structured email body from the finding's own fields
    (not just alert.message), so the recipient gets full context: company,
    product, regulation, the specific gap, deadline, severity, recommended
    action, and the source citation.
    """
    lines = []

    company = finding.get("company")
    product = finding.get("product")
    if company and product:
        lines.append(f"Company: {company}")
        lines.append(f"Product: {product} (Product ID: {finding.get('product_id', 'n/a')})")
        lines.append("")

    regulation = finding.get("regulation")
    if regulation:
        lines.append(f"Regulation: {regulation}")

    requirement = finding.get("requirement")
    if requirement:
        lines.append(f"Requirement: {requirement}")

    gap = finding.get("gap")
    if gap:
        lines.append("")
        lines.append(f"Gap identified: {gap}")

    severity = finding.get("severity")
    deadline = finding.get("deadline")
    if severity or deadline:
        lines.append("")
        if severity:
            lines.append(f"Severity: {severity.upper()}")
        if deadline:
            lines.append(f"Deadline: {deadline}")

    recommended_action = finding.get("recommended_action")
    if recommended_action:
        lines.append("")
        lines.append(f"Recommended action: {recommended_action}")

    source_url = finding.get("source_url")
    if source_url:
        lines.append("")
        lines.append(f"Source: {source_url}")

    # Fall back to the alert's own message if the finding is missing most
    # structured fields (e.g. a minimal/custom finding shape).
    if not lines:
        return finding.get("alert", {}).get("message", "")

    return "\n".join(lines)


def send_email(sendgrid_cfg: SendGridConfig, finding: dict, dry_run: bool) -> Optional[str]:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    alert = finding["alert"]
    to_email = alert["to"]
    body = build_email_body(finding)
    subject = alert.get("subject") or f"Compliance alert: {finding.get('company', '')} - {finding.get('product', '')}"

    log.info(
        "Preparing email alert for %s / %s -> %s%s",
        finding.get("company"), finding.get("product"), to_email,
        f" (data residency: {sendgrid_cfg.data_residency})" if sendgrid_cfg.data_residency else "",
    )

    if dry_run:
        log.info("[DRY RUN] Would send email. Subject=%r\n%s", subject, body)
        return None

    mail = Mail(
        from_email=sendgrid_cfg.from_email,
        to_emails=to_email,
        subject=subject,
        plain_text_content=body,
    )
    sg_client = SendGridAPIClient(sendgrid_cfg.api_key)
    if sendgrid_cfg.data_residency:
        # Routes the request through SendGrid's EU infrastructure instead
        # of the global default. Relevant for EU-based senders/recipients
        # under GDPR-style data-handling requirements.
        sg_client.set_sendgrid_data_residency(sendgrid_cfg.data_residency)

    try:
        response = sg_client.send(mail)
    except Exception as e:
        # The SendGrid SDK's HTTPError exposes the real error detail in
        # .body (bytes, usually JSON) -- the bare exception message alone
        # (e.g. "HTTP Error 401: Unauthorized") doesn't say *why*. Report
        # everything we can find, even if some fields are empty, so the
        # cause isn't silently swallowed.
        status_code = getattr(e, "status_code", None)
        reason = getattr(e, "reason", None)
        body = getattr(e, "body", None)
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")

        hint = ""
        if status_code == 401:
            hint = (
                " (A 401 from SendGrid almost always means the API key is "
                "invalid, was revoked/rotated, or lacks 'Mail Send' "
                "permission. It can also mean SENDGRID_API_KEY wasn't "
                "picked up correctly in this shell session.)"
            )
        elif status_code == 403:
            hint = (
                " (A 403 from SendGrid often means the 'from' address "
                "isn't a verified Sender Identity/domain.)"
            )

        raise RuntimeError(
            f"SendGrid error: {e} | status_code={status_code} reason={reason!r} "
            f"body={body!r}{hint}"
        ) from e

    log.info("Sent. SendGrid status_code=%s", response.status_code)
    return str(response.status_code)


# ============================================================
# Orchestration
# ============================================================

def process_findings(findings: Iterable[dict], dry_run: bool = False) -> dict:
    """
    Sends alerts for all findings, routed by channel. Returns a summary
    dict with counts and any errors, so a calling agent/pipeline can act
    on results.
    """
    twilio_cfg = TwilioConfig.from_env()
    sendgrid_cfg = SendGridConfig.from_env()
    twilio_client = twilio_cfg.make_client() if twilio_cfg else None

    if not twilio_cfg:
        log.warning(
            "Twilio is not configured (TWILIO_ACCOUNT_SID not set) -- "
            "sms/whatsapp findings will be skipped."
        )
    if not sendgrid_cfg:
        log.warning(
            "SendGrid is not configured (SENDGRID_API_KEY/SENDGRID_FROM_EMAIL "
            "not set) -- email findings will be skipped."
        )

    results = {"sent": [], "skipped": [], "failed": []}

    for finding in findings:
        identifier = f"{finding.get('partner_id', '?')}/{finding.get('product_id', '?')}"
        try:
            validate_finding(finding)
            channel = finding["alert"]["channel"]

            if channel in ("sms", "whatsapp"):
                if not twilio_client:
                    raise RuntimeError("Twilio is not configured; cannot send sms/whatsapp.")
                ref = send_sms_or_whatsapp(twilio_client, twilio_cfg, finding, dry_run)
            else:  # email
                if not sendgrid_cfg:
                    raise RuntimeError("SendGrid is not configured; cannot send email.")
                ref = send_email(sendgrid_cfg, finding, dry_run)

            results["sent"].append({"id": identifier, "channel": channel, "ref": ref})

        except ValueError as e:
            log.warning("Skipping invalid finding %s: %s", identifier, e)
            results["skipped"].append({"id": identifier, "reason": str(e)})
        except TwilioRestException as e:
            log.error("Twilio API error for %s: %s", identifier, e)
            results["failed"].append({"id": identifier, "reason": str(e)})
        except Exception as e:
            log.error("Error sending alert for %s: %s", identifier, e)
            results["failed"].append({"id": identifier, "reason": str(e)})

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Send SMS/WhatsApp/email alerts for regulatory-compliance findings."
    )
    parser.add_argument(
        "source",
        help="Path to a JSON file containing one finding or a list of findings, "
             "or a raw JSON string.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and log what would be sent, without actually sending.",
    )
    args = parser.parse_args()

    findings = load_findings(args.source)
    log.info("Loaded %d finding(s) from %s", len(findings), args.source)

    summary = process_findings(findings, dry_run=args.dry_run)

    log.info(
        "Done. sent=%d skipped=%d failed=%d",
        len(summary["sent"]), len(summary["skipped"]), len(summary["failed"]),
    )
    if summary["failed"] or summary["skipped"]:
        log.info("Details: %s", json.dumps(summary, indent=2))

    sys.exit(1 if summary["failed"] else 0)


if __name__ == "__main__":
    main()
