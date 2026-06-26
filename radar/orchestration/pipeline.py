"""Shared pipeline orchestration for CLI and web."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime

from radar.compliance.evaluate import evaluate
from radar.ingest import ingest
from radar import mcp
from radar.alerts import notify
from radar.config import STATE_FILE, env, load_dotenv
import json

_job_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def _save_last_run(result: dict) -> None:
    if not STATE_FILE.exists():
        return
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    state["last_run"] = result.get("finished") or datetime.utcnow().isoformat() + "Z"
    state["last_pipeline"] = {
        "gaps_found": result.get("gaps_found", 0),
        "ingested_new": result.get("ingested_new", 0),
        "alerts_sent": result.get("alerts_sent", 0),
    }
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def alerts_enabled(send_alerts: bool = True) -> bool:
    """Honour --no-alert, SKIP_TWILIO=1, or missing Twilio credentials."""
    load_dotenv()
    if not send_alerts:
        return False
    if env("SKIP_TWILIO", "").lower() in ("1", "true", "yes"):
        return False
    if not env("TWILIO_ACCOUNT_SID") or not env("TWILIO_AUTH_TOKEN"):
        return False
    return True


def run_pipeline(send_alerts: bool = True) -> dict:
    load_dotenv()
    job_id = str(uuid.uuid4())[:8]
    with _job_lock:
        _jobs[job_id] = {"status": "running", "started": datetime.utcnow().isoformat() + "Z"}

    try:
        mcp_stats = mcp.run()
        gaps = evaluate()
        do_alert = alerts_enabled(send_alerts)
        if not do_alert:
            print("Alerts skipped (SKIP_TWILIO or Twilio credentials not set)")
        alert_results = notify.alert_all() if do_alert else []
        result = {
            "job_id": job_id,
            "status": "completed",
            "ingested_new": mcp_stats.get("ingested_new", 0),
            "mcp": mcp_stats,
            "gaps_found": len(gaps),
            "alerts_sent": sum(1 for a in alert_results if a.get("status") == "sent"),
        }
    except Exception as e:
        result = {"job_id": job_id, "status": "failed", "error": str(e)}

    with _job_lock:
        _jobs[job_id] = {**result, "finished": datetime.utcnow().isoformat() + "Z"}
    if result.get("status") == "completed":
        _save_last_run(_jobs[job_id])
    return result


def run_pipeline_async(send_alerts: bool = True) -> str:
    job_id = str(uuid.uuid4())[:8]
    with _job_lock:
        _jobs[job_id] = {"status": "queued", "started": datetime.utcnow().isoformat() + "Z"}

    def _work():
        with _job_lock:
            _jobs[job_id]["status"] = "running"
        try:
            mcp_stats = mcp.run()
            gaps = evaluate()
            do_alert = alerts_enabled(send_alerts)
            alert_results = notify.alert_all() if do_alert else []
            finished = datetime.utcnow().isoformat() + "Z"
            with _job_lock:
                _jobs[job_id] = {
                    "job_id": job_id,
                    "status": "completed",
                    "ingested_new": mcp_stats.get("ingested_new", 0),
                    "mcp": mcp_stats,
                    "gaps_found": len(gaps),
                    "alerts_sent": sum(1 for a in alert_results if a.get("status") == "sent"),
                    "finished": finished,
                }
            _save_last_run(_jobs[job_id])
        except Exception as e:
            with _job_lock:
                _jobs[job_id] = {
                    "job_id": job_id,
                    "status": "failed",
                    "error": str(e),
                    "finished": datetime.utcnow().isoformat() + "Z",
                }

    threading.Thread(target=_work, daemon=True).start()
    return job_id


def get_job(job_id: str) -> dict | None:
    with _job_lock:
        return _jobs.get(job_id)
