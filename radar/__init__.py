"""Regulatory Radar — monitor → assess → alert pipeline.

Package layout (by functionality):
  api/            FastAPI dashboard, chat lookup, static UI
  mcp/            MCP orchestration, embed, router, vectordb
  ingest/         Live API fetch, translate, ECHA, regulation cache
  compliance/     Gap evaluation, scoring, taxonomy, findings
  alerts/         Alert messages and Twilio notify
  review/         Human-in-the-loop queue
  orchestration/  Full pipeline (ingest → evaluate → alert)
  config.py       Shared paths and environment
"""
