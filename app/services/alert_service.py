from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models import Alert, AlertType, Instance
from app.models.models import utcnow
from app.pagination import DEFAULT_SIZE, paginate


def list_alerts(
    db: Session,
    client_ids: list[int] | None,
    page: int = 1,
    size: int = DEFAULT_SIZE,
    alertType: AlertType | None = None,
    isResolved: bool | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
) -> tuple[list[Alert], int, int]:
    """One page of alert history, newest `detectedAt` first.

    `alerts` is the fastest-growing table in the schema — the monitoring scans append to
    it and nothing prunes it — so this is the endpoint that most needed a bound:
    unpaginated it loaded and serialised every alert the caller could see
    (docs/performance/PERFORMANCE_BUGS.md § PERF-07).
    """
    query = db.query(Alert).join(Instance, Alert.instanceId == Instance.id)
    if client_ids is not None:
        query = query.filter(Instance.clientId.in_(client_ids or [-1]))
    if alertType is not None:
        query = query.filter(Alert.alertType == alertType)
    if isResolved is not None:
        query = query.filter(Alert.isResolved.is_(isResolved))
    if dateFrom is not None:
        query = query.filter(Alert.detectedAt >= datetime.combine(dateFrom, time.min))
    if dateTo is not None:
        query = query.filter(Alert.detectedAt <= datetime.combine(dateTo, time.max))
    # `id` breaks ties on `detectedAt`. A scan stamps every alert it records with the
    # same instant, so without a unique second key the rows in a tie could come back in
    # any order and an alert could appear on two pages or on none.
    query = query.order_by(Alert.detectedAt.desc(), Alert.id.desc())
    return paginate(query, Alert.id, page, size)


def resolve_alert(db: Session, alert_id: int) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise NotFoundException("Alert", alert_id)
    if not alert.isResolved:
        alert.isResolved = True
        alert.resolvedAt = utcnow()
        db.commit()
        db.refresh(alert)
    return alert
