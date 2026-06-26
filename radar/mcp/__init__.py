"""
MCP package — regulation library + optional ingest pipeline.

Transplant guide: radar/mcp/README.md
Public API:        radar.mcp.contract
HTTP routes:       radar.mcp.routes.router
"""

from __future__ import annotations

# --- Regulation contract (team lead: fetchregulation + check) ---
from radar.mcp import label_regs
from radar.mcp.regulation_ops import check, check_label, fetch_regulation, fetchregulation

# --- Optional pipeline (API-key ingest → embed → route → HIL) ---
from radar.mcp.run import API_SOURCES, credentials_status, enrich_cache, fetch_from_apis, run

__all__ = [
    # Contract
    "check",
    "check_label",
    "fetch_regulation",
    "fetchregulation",
    "label_regs",
    # Pipeline
    "API_SOURCES",
    "credentials_status",
    "enrich_cache",
    "fetch_from_apis",
    "run",
]
