"""Dashboard metrics, manual scan trigger, taxonomy + users."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import label_map, models, taxonomy, vector_store
from ..database import get_db
from ..schemas import DashboardMetrics, LoginRequest, ScanResult, UserOut
from ..services.analytics import compute_analytics, compute_product_analytics
from ..services.gap_analysis import run_sync

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/dashboard/metrics", response_model=DashboardMetrics)
def dashboard_metrics(
    user_id: str | None = None, db: Session = Depends(get_db)
) -> DashboardMetrics:
    prod_stmt = select(func.count(models.Product.id))
    alert_stmt = (
        select(func.count(models.Alert.id))
        .join(models.Product)
        .where(models.Alert.is_read == False)  # noqa: E712
    )
    if user_id:
        prod_stmt = prod_stmt.where(models.Product.user_id == user_id)
        alert_stmt = alert_stmt.where(models.Product.user_id == user_id)

    total_products = db.execute(prod_stmt).scalar() or 0
    active_alerts = db.execute(alert_stmt).scalar() or 0

    # Distinct regulation families covered across the portfolio.
    p_stmt = select(models.Product)
    if user_id:
        p_stmt = p_stmt.where(models.Product.user_id == user_id)
    products = db.execute(p_stmt).scalars().all()
    families: set[str] = set()
    for p in products:
        families.update(p.compliance_streams or [])
    monitored = len(families) or len(taxonomy.regulation_families())

    return DashboardMetrics(
        total_products=total_products,
        active_alerts=active_alerts,
        monitored_regulations=monitored,
    )


@router.get("/analytics")
def analytics(user_id: str | None = None, db: Session = Depends(get_db)) -> dict:
    return compute_analytics(db, user_id)


@router.get("/analytics/product/{product_id}")
def product_analytics(product_id: str, db: Session = Depends(get_db)) -> dict:
    from fastapi import HTTPException

    result = compute_product_analytics(db, product_id)
    if result is None:
        raise HTTPException(404, "product not found")
    return result


@router.post("/scan", response_model=ScanResult)
def trigger_scan(db: Session = Depends(get_db)) -> ScanResult:
    """Manually run the daily MCP sync now (Workflows B + C)."""
    return run_sync(db)


@router.get("/taxonomy")
def get_taxonomy() -> dict:
    return taxonomy.get_taxonomy()


@router.get("/labels")
def get_labels() -> list[dict]:
    """The canonical label map (labels.md) — the only labels the system uses."""
    return [
        {
            "label": d.label,
            "regulation": d.regulation,
            "source": d.source,
            "source_url": d.source_url,
            "triggers": d.triggers,
        }
        for d in label_map.load_labels().values()
    ]


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[UserOut]:
    users = db.execute(select(models.User).order_by(models.User.company_name)).scalars().all()
    return [UserOut.model_validate(u) for u in users]


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> UserOut:
    """Resolve a partner ID (e.g. 'P001' or '1') to its company user."""
    pid = payload.partner_id.strip().upper()
    if pid.isdigit():  # accept bare numbers: 1 -> P001
        pid = f"P{int(pid):03d}"
    user = db.execute(
        select(models.User).where(models.User.partner_id == pid)
    ).scalars().first()
    if not user:
        from fastapi import HTTPException

        raise HTTPException(404, f"No company found for partner ID '{payload.partner_id}'")
    return UserOut.model_validate(user)


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "vector_chunks": vector_store.count()}
