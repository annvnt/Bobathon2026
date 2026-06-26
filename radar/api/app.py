"""FastAPI dashboard — reads same JSON files as CLI."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from radar.api import chat
from radar.compliance import findings
from radar.review import hil
from radar import mcp
from radar.mcp.routes import router as mcp_router
from radar.orchestration import pipeline
from radar.ingest import regcache
from radar.config import CACHE_FILE, GAPS_FILE, HIL_QUEUE_FILE, STATE_FILE, VECTORDB_FILE, load_dotenv

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Regulatory Radar", version="1.0.0")
load_dotenv()
app.include_router(mcp_router)


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/status")
def api_status():
    state = _read_json(STATE_FILE, {})
    cache = _read_json(CACHE_FILE, {"updates": []})
    gaps = _read_json(GAPS_FILE, [])
    updates = cache.get("updates", []) if isinstance(cache, dict) else cache
    last_run = state.get("last_run")
    if not last_run:
        for src in state.values():
            if isinstance(src, dict) and src.get("last_run"):
                last_run = src["last_run"]
                break
    return {
        "last_run": last_run,
        "update_count": len(updates),
        "gap_count": len(gaps),
        "alerts_sent": state.get("last_pipeline", {}).get("alerts_sent", 0),
        "hil_pending": len(hil.list_pending()),
        "vector_entries": len(_read_json(VECTORDB_FILE, {}).get("entries", [])),
        "api_credentials": mcp.credentials_status(),
        "regulation_cache": regcache.stats(),
        "sources": {k: v for k, v in state.items() if isinstance(v, dict)},
    }


def _filter_gaps(
    gaps: list,
    *,
    severity: str | None = None,
    criticality: str | None = None,
    urgency: str | None = None,
    family: str | None = None,
    status: str | None = None,
    partner_id: str | None = None,
    q: str | None = None,
) -> list:
    out = gaps
    if severity:
        out = [g for g in out if g.get("severity") == severity]
    if criticality:
        out = [g for g in out if g.get("criticality") == criticality]
    if urgency:
        out = [g for g in out if g.get("urgency") == urgency]
    if family:
        out = [g for g in out if g.get("regulation_family") == family]
    if status:
        out = [g for g in out if g.get("status") == status]
    if partner_id:
        out = [g for g in out if g.get("partner_id") == partner_id]
    if q:
        ql = q.lower()
        out = [
            g for g in out
            if ql in (g.get("company") or "").lower()
            or ql in (g.get("product") or "").lower()
            or ql in (g.get("regulation") or "").lower()
            or ql in (g.get("gap") or "").lower()
        ]
    return [findings.merge_into_gap(g) for g in out]


@app.get("/api/gaps")
def api_gaps(
    severity: str | None = Query(None),
    criticality: str | None = Query(None),
    urgency: str | None = Query(None),
    family: str | None = Query(None),
    status: str | None = Query(None),
    partner_id: str | None = Query(None),
    q: str | None = Query(None),
):
    gaps = _read_json(GAPS_FILE, [])
    return _filter_gaps(
        gaps,
        severity=severity,
        criticality=criticality,
        urgency=urgency,
        family=family,
        status=status,
        partner_id=partner_id,
        q=q,
    )


@app.get("/api/gaps/{finding_id}")
def api_gap_detail(finding_id: str):
    gaps = _read_json(GAPS_FILE, [])
    for g in gaps:
        if g.get("finding_id") == finding_id:
            return findings.merge_into_gap(g)
    return JSONResponse({"status": "not_found"}, status_code=404)


class GapStatusUpdate(BaseModel):
    status: str
    note: str = ""


@app.post("/api/gaps/{finding_id}/status")
def api_gap_status(finding_id: str, body: GapStatusUpdate):
    try:
        entry = findings.set_status(finding_id, body.status, note=body.note)
        return {"finding_id": finding_id, **entry}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/regulations/library")
def api_regulation_library():
    """Regulation library (A4): cached texts + ingested updates."""
    entries = {e["key"]: e for e in regcache.list_cached()}
    cache = _read_json(CACHE_FILE, {"updates": []})
    for u in cache.get("updates", []):
        key = u.get("regulation_text_key")
        if not key:
            continue
        if key not in entries:
            entries[key] = {
                "key": key,
                "title": u.get("title"),
                "reference": u.get("reference"),
                "source": u.get("source"),
                "regulation_family": u.get("regulation_family"),
                "url": u.get("source_url"),
            }
    return list(entries.values())


@app.get("/api/alert-log")
def api_alert_log():
    from radar.compliance.findings import ALERT_LOG_FILE
    return _read_json(ALERT_LOG_FILE, [])


@app.get("/api/oj/recent")
def api_oj_recent(since: str = Query("2026-01-01"), limit: int = Query(30, ge=1, le=100)):
    """Recent Official Journal acts from EUR-Lex RSS (L + C series)."""
    from radar.ingest import oj_rss as oj_mod
    from radar.ingest import translate as tr

    raw = oj_mod.fetch_oj_rss_raw(since)
    records = [tr.from_oj_rss(h) for h in raw[:limit]]
    return {
        "since": since,
        "count": len(records),
        "feeds": oj_mod.OJ_RSS_FEEDS,
        "updates": records,
    }


@app.get("/api/updates")
def api_updates(limit: int = Query(50, ge=1, le=200)):
    cache = _read_json(CACHE_FILE, {"updates": []})
    updates = cache.get("updates", [])
    updates = sorted(updates, key=lambda u: u.get("published_date", ""), reverse=True)
    return updates[:limit]


@app.post("/api/run")
def api_run():
    job_id = pipeline.run_pipeline_async()
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/hil")
def api_hil():
    return hil.list_pending()


@app.post("/api/hil/{item_id}/approve")
def api_hil_approve(item_id: str, chosen_match_id: str | None = None):
    item = hil.approve(item_id, chosen_match_id)
    if not item:
        return {"status": "not_found"}
    return {"status": "approved", "item": item}


@app.get("/api/regulations/{cache_key}")
def api_regulation_by_key(cache_key: str):
    rec = regcache.get_by_key(cache_key)
    if rec:
        return rec
    return {"status": "not_found", "key": cache_key}


@app.get("/api/regulations")
def api_regulation_lookup(
    source: str = Query(...),
    reference: str = Query(...),
    title: str = Query(""),
    force: bool = Query(False),
):
    """Return cached regulation text, fetching from API only on first request."""
    rec = regcache.get_or_fetch(source, reference, title or reference, force=force)
    return rec


class ChatRequest(BaseModel):
    query: str


@app.post("/api/chat/lookup")
def api_chat_lookup(body: ChatRequest):
    """Match product / ingredient text to EUR-Lex and Open Legal Data regulations."""
    result = chat.lookup(body.query.strip())
    if result.get("error"):
        return JSONResponse(result, status_code=400)
    return result


@app.get("/api/job/{job_id}")
def api_job(job_id: str):
    job = pipeline.get_job(job_id)
    if not job:
        return {"status": "unknown"}
    return job


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
