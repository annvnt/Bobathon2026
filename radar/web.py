"""FastAPI dashboard — reads same JSON files as CLI."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from radar import hil, mcp, pipeline, regcache
from radar.config import CACHE_FILE, GAPS_FILE, HIL_QUEUE_FILE, STATE_FILE, VECTORDB_FILE, load_dotenv

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Regulatory Radar", version="1.0.0")
load_dotenv()


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


@app.get("/api/gaps")
def api_gaps(severity: str | None = Query(None)):
    gaps = _read_json(GAPS_FILE, [])
    if severity:
        gaps = [g for g in gaps if g.get("severity") == severity]
    return gaps


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
