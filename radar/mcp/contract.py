"""
Team MCP public contract — import only from here when transplanting.

Tech-lead surface:
  fetch_regulation() / fetchregulation()
  check_label() / check()

Regulation library:
  fetch_by_code()          CELEX or GADI abbrev
  get_regulations()
  store_product_regulations()
  resolve_labels()
  STREAM_REG_CODES

Portfolio / presentation (optional; needs Dataset/partners.json):
  catalog_status()
  fetch_portfolio_catalog()
  present_regulations()
  list_products()
"""

from __future__ import annotations

from radar.mcp import label_regs
from radar.mcp.catalog import catalog_status, fetch_portfolio_catalog, portfolio_streams
from radar.mcp.present import list_products, present_regulations
from radar.mcp.regulation_ops import check, check_label, fetch_regulation, fetchregulation

# Re-export code / stream registry
STREAM_REG_CODES = label_regs.STREAM_REG_CODES
PORTFOLIO_COMPLIANCE_STREAMS = label_regs.PORTFOLIO_COMPLIANCE_STREAMS
EU_LABEL_CELEX = label_regs.EU_LABEL_CELEX
fetch_by_code = label_regs.fetch_by_code
get_regulations = label_regs.get_regulations
resolve_labels = label_regs.resolve_labels
store_product_regulations = label_regs.store_product_regulations
regulations_for_labels = label_regs.regulations_for_labels
append_regulation = label_regs.append_regulation
is_celex = label_regs.is_celex
codes_for_stream = label_regs.codes_for_stream

__all__ = [
    "STREAM_REG_CODES",
    "PORTFOLIO_COMPLIANCE_STREAMS",
    "EU_LABEL_CELEX",
    "append_regulation",
    "catalog_status",
    "check",
    "check_label",
    "codes_for_stream",
    "fetch_by_code",
    "fetch_portfolio_catalog",
    "fetch_regulation",
    "fetchregulation",
    "get_regulations",
    "is_celex",
    "list_products",
    "portfolio_streams",
    "present_regulations",
    "regulations_for_labels",
    "resolve_labels",
    "store_product_regulations",
]
