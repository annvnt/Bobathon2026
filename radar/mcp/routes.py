"""FastAPI routes for MCP — mount with app.include_router(mcp_router)."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from radar.mcp import catalog as mcp_catalog
from radar.mcp import label_regs
from radar.mcp import present as mcp_present
from radar.mcp.regulation_ops import check_label, fetch_regulation

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class LabelRegulationsRequest(BaseModel):
    product_id: str
    labels: list[str]
    countries: list[str]


class PresentRegulationsRequest(BaseModel):
    product_id: str | None = None
    labels: list[str] | None = None
    countries: list[str] | None = None
    save: bool = False


class FetchRegulationRequest(BaseModel):
    labels: list[str]
    countries: list[str]
    product_id: str = ""
    save: bool = True


class FetchCatalogRequest(BaseModel):
    countries: list[str] = ["EU", "DE"]
    save: bool = True


@router.post("/label-regulations")
def api_mcp_label_regulations(body: LabelRegulationsRequest):
    if not body.labels:
        return JSONResponse({"error": "labels required"}, status_code=400)
    if not body.countries:
        return JSONResponse({"error": "countries required (e.g. DE, EU)"}, status_code=400)
    stored = label_regs.store_product_regulations(
        body.product_id.strip(),
        body.labels,
        body.countries,
    )
    return {"product_id": body.product_id.strip(), **stored}


@router.get("/label-regulations")
def api_mcp_label_regulations_list(
    category: str = Query(""),
    country: str = Query(""),
    code: str = Query(""),
):
    return label_regs.get_regulations(
        category=category or None,
        country=country or None,
        code=code or None,
    )


@router.get("/code/{code}")
def api_mcp_fetch_by_code(code: str, stream: str = Query(""), save: bool = Query(False)):
    rec = label_regs.fetch_by_code(code, stream=stream)
    if not rec:
        return JSONResponse({"error": "not_found", "code": code}, status_code=404)
    if save:
        label_regs.append_regulation(rec)
    return rec


@router.get("/codes")
def api_mcp_stream_codes():
    return {"streams": label_regs.STREAM_REG_CODES}


@router.get("/catalog")
def api_mcp_catalog(countries: str = Query("EU,DE")):
    country_list = [c.strip() for c in countries.split(",") if c.strip()]
    return mcp_catalog.catalog_status(country_list or None)


@router.post("/fetch-catalog")
def api_mcp_fetch_catalog(body: FetchCatalogRequest):
    return mcp_catalog.fetch_portfolio_catalog(body.countries, save=body.save)


@router.post("/label-regulations/preview")
def api_mcp_label_regulations_preview(body: LabelRegulationsRequest):
    if not body.labels or not body.countries:
        return JSONResponse({"error": "labels and countries required"}, status_code=400)
    return label_regs.resolve_labels(
        body.labels,
        body.countries,
        product_id=body.product_id or None,
    )


@router.post("/fetch-regulation")
def api_mcp_fetch_regulation(body: FetchRegulationRequest):
    result = fetch_regulation(
        body.labels,
        body.countries,
        product_id=body.product_id,
        save=body.save,
    )
    if result.get("error"):
        return JSONResponse(result, status_code=400)
    return result


@router.get("/check/{label}")
def api_mcp_check_label(
    label: str,
    since: str = Query(""),
    include_cache: bool = Query(True),
    limit: int = Query(20, ge=1, le=100),
):
    result = check_label(
        label,
        since=since or None,
        include_cache=include_cache,
        oj_limit=limit,
    )
    if result.get("error"):
        return JSONResponse(result, status_code=400)
    return result


@router.get("/products")
def api_mcp_products():
    return {"products": mcp_present.list_products()}


@router.post("/present")
def api_mcp_present(body: PresentRegulationsRequest):
    result = mcp_present.present_regulations(
        product_id=body.product_id,
        labels=body.labels,
        countries=body.countries,
        save=body.save,
    )
    if result.get("error"):
        return JSONResponse(result, status_code=400)
    return result
