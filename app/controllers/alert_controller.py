from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.deps import accessible_client_ids, assert_client_id_access, get_current_member
from app.database import get_db
from app.models import AlertType, Member
from app.pagination import DEFAULT_SIZE, PageParam, SizeParam
from app.schemas.schemas import AlertOut, PageResponse
from app.services import alert_service

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get(
    "",
    response_model=PageResponse[AlertOut],
    summary="Alert history (pagination / date / type / resolved filter)",
)
def list_alerts(
    page: PageParam = 1,
    size: SizeParam = DEFAULT_SIZE,
    alertType: AlertType | None = Query(None, description="Filter by alert type"),
    isResolved: bool | None = Query(None, description="Filter by resolved state"),
    dateFrom: date | None = Query(None, description="Detected on/after (YYYY-MM-DD)"),
    dateTo: date | None = Query(None, description="Detected on/before (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    items, total, total_pages = alert_service.list_alerts(
        db,
        accessible_client_ids(member),
        page=page,
        size=size,
        alertType=alertType,
        isResolved=isResolved,
        dateFrom=dateFrom,
        dateTo=dateTo,
    )
    return PageResponse(
        items=items, total=total, page=page, size=size, totalPages=total_pages
    )


@router.patch("/{alert_id}/resolve", response_model=AlertOut, summary="Mark Alert as resolved")
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    from app.models import Alert

    # The alert's instance comes back with it rather than on a lazy load of its own: the
    # authorization check below is the only reader, and it needs one column,
    # `clientId`. Reaching it as `alert.instance.client` cost two chained loads — the
    # instance, then a whole `Client` row to compare one integer
    # (docs/performance/PERFORMANCE_BUGS.md § PERF-11).
    alert = db.get(Alert, alert_id, options=[joinedload(Alert.instance)])
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    assert_client_id_access(db, member, alert.instance.clientId)
    return alert_service.resolve_alert(db, alert_id)
