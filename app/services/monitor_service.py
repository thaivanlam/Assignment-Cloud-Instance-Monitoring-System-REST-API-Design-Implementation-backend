from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import Select, func, insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Alert, AlertType, Instance, InstanceStatus
from app.models.models import utcnow
from app.pagination import DEFAULT_SIZE

# A scan walks its instances in batches of this size. Two things set it: the dedup probe
# reads a whole batch of ids in one statement and SQLite caps a statement at 32766 bind
# parameters, and a scan must record an alert for every matching instance even though it
# returns only one page of them — so it holds a batch in memory rather than the whole
# result set, however large that grows.
ID_BATCH_SIZE = 500

# The report embeds only the most recent unresolved alerts; the full history is
# GET /api/alerts.  See docs/performance/PERFORMANCE_BUGS.md § PERF-07.
REPORT_ALERT_LIMIT = 20


def _instances_with_unresolved_alert(
    db: Session, instance_ids: list[int], alert_type: AlertType
) -> set[int]:
    """The subset of `instance_ids` that already carries an unresolved alert of this type.

    `instance_ids` is one scan batch, so this is a single statement whose bind-parameter
    count is bounded by `ID_BATCH_SIZE`.
    """
    return {
        row[0]
        for row in db.query(Alert.instanceId).filter(
            Alert.instanceId.in_(instance_ids),
            Alert.alertType == alert_type,
            Alert.isResolved.is_(False),
        )
    }


def _record_alerts(
    db: Session,
    instances: list[Instance],
    alert_type: AlertType,
    message: Callable[[Instance], str],
) -> bool:
    """Records one alert per instance that has no unresolved alert of this type yet.

    The dedup rule is unchanged (docs/business-rules/ALERTING.md § 3) — an instance with
    an open alert of the same type is still skipped. What changed is the number of
    statements: a whole batch is checked in one query rather than one instance at a
    time, and the new alerts are inserted together. See
    docs/performance/PERFORMANCE_BUGS.md § PERF-05.

    `instances` is one scan batch of at most `ID_BATCH_SIZE`; `_scan` calls this once per
    batch, so a scan of any size costs two statements per batch rather than two per
    instance.

    Returns True if at least one new alert was created.
    """
    if not instances:
        return False
    existing = _instances_with_unresolved_alert(db, [i.id for i in instances], alert_type)
    new_alerts = [
        {"instanceId": inst.id, "alertType": alert_type, "message": message(inst)}
        for inst in instances
        if inst.id not in existing
    ]
    if not new_alerts:
        return False
    # A Core insert rather than `db.add_all`: the ORM cannot batch inserts that need
    # their generated ids back on SQLite, so `add_all` would still be one statement per
    # alert. Nothing here uses the rows once written — the scan returns instances — so
    # the ids are not needed and the whole batch goes in one executemany. `isResolved`
    # and `detectedAt` still come from the column defaults declared on the model.
    db.execute(insert(Alert), new_alerts)
    return True


def _scan(
    db: Session,
    query,
    alert_type: AlertType,
    message: Callable[[Instance], str],
    page: int,
    size: int,
) -> tuple[list[Instance], int, int]:
    """Run one detection scan: record alerts for every match, return one page of them.

    Detection and the response are deliberately not the same set. The endpoint records a
    `CPU_HIGH` for the 700th high-CPU instance just as it does for the first, because the
    alert is the point of the scan (docs/business-rules/ALERTING.md § 2) — paginating the
    *recording* would silently stop detecting past page one. Only the response is
    paginated (docs/performance/PERFORMANCE_BUGS.md § PERF-07).

    That is why this walks the matches itself instead of calling `paginate`: one pass
    over the result, in id-keyset batches, both records the alerts and picks out the
    requested window, so `total` and the page fall out of the walk with no extra count
    or offset query. At most `ID_BATCH_SIZE` instances plus one page are held at a time,
    so a scan that matches the whole table no longer materialises the whole table.
    """
    window = range((page - 1) * size, (page - 1) * size + size)
    items: list[Instance] = []
    total = 0
    recorded = False
    last_id = 0

    while True:
        batch = (
            query.filter(Instance.id > last_id)
            .order_by(Instance.id)
            .limit(ID_BATCH_SIZE)
            .all()
        )
        if not batch:
            break
        recorded |= _record_alerts(db, batch, alert_type, message)
        for instance in batch:
            if total in window:
                items.append(instance)
            total += 1
        last_id = batch[-1].id
        if len(batch) < ID_BATCH_SIZE:
            break

    _commit_if_recorded(db, recorded)
    total_pages = (total + size - 1) // size
    return items, total, total_pages


def _commit_if_recorded(db: Session, recorded: bool) -> None:
    """Commits a scan only when it actually opened a new alert.

    A scan that finds nothing new is a pure read, and committing one would still take
    SQLite's write lock and fsync — serialising every other request behind a dashboard
    poll that changed nothing. Dedup means most polls are exactly that case.
    """
    if recorded:
        db.commit()


def check_warnings(
    db: Session,
    client_ids: Select[tuple[int]] | None,
    page: int = 1,
    size: int = DEFAULT_SIZE,
) -> tuple[list[Instance], int, int]:
    """CPU >= 80% instances; auto-records a CPU_HIGH alert for each (skip if
    an unresolved CPU_HIGH alert already exists). Returns one page of the matches."""
    query = db.query(Instance).filter(
        Instance.cpuUsage >= settings.CPU_WARNING_THRESHOLD,
        Instance.status == InstanceStatus.RUNNING,
    )
    if client_ids is not None:
        query = query.filter(Instance.clientId.in_(client_ids))

    return _scan(
        db, query, AlertType.CPU_HIGH,
        lambda inst: (
            f"CPU usage {inst.cpuUsage:.1f}% >= {settings.CPU_WARNING_THRESHOLD:.0f}% "
            f"on instance '{inst.instanceName}' ({inst.region})"
        ),
        page, size,
    )


def check_errors(
    db: Session,
    client_ids: Select[tuple[int]] | None,
    page: int = 1,
    size: int = DEFAULT_SIZE,
) -> tuple[list[Instance], int, int]:
    """ERROR status instances; auto-records a critical ERROR_DETECTED alert.
    Returns one page of the matches."""
    query = db.query(Instance).filter(Instance.status == InstanceStatus.ERROR)
    if client_ids is not None:
        query = query.filter(Instance.clientId.in_(client_ids))

    return _scan(
        db, query, AlertType.ERROR_DETECTED,
        lambda inst: (
            f"[CRITICAL] Instance '{inst.instanceName}' ({inst.region}) is in ERROR state"
        ),
        page, size,
    )


def check_long_stopped(
    db: Session,
    client_ids: Select[tuple[int]] | None,
    page: int = 1,
    size: int = DEFAULT_SIZE,
) -> tuple[list[Instance], int, int]:
    """Instances STOPPED for 48+ hours (based on last status update time).
    Also records a LONG_STOPPED alert for visibility. Returns one page of the matches."""
    now = utcnow()
    threshold = now - timedelta(hours=settings.LONG_STOPPED_HOURS)
    query = db.query(Instance).filter(
        Instance.status == InstanceStatus.STOPPED,
        Instance.updatedAt <= threshold,
    )
    if client_ids is not None:
        query = query.filter(Instance.clientId.in_(client_ids))

    def stopped_message(inst: Instance) -> str:
        hours = (now - inst.updatedAt).total_seconds() / 3600
        return (
            f"Instance '{inst.instanceName}' has been STOPPED for {hours:.0f} hours "
            f"(>= {settings.LONG_STOPPED_HOURS}h)"
        )

    return _scan(db, query, AlertType.LONG_STOPPED, stopped_message, page, size)


def build_report(db: Session, client_ids: Select[tuple[int]] | None) -> dict:
    inst_query = db.query(Instance)
    alert_query = db.query(Alert).join(Instance, Alert.instanceId == Instance.id)
    if client_ids is not None:
        inst_query = inst_query.filter(Instance.clientId.in_(client_ids))
        alert_query = alert_query.filter(Instance.clientId.in_(client_ids))

    status_counts = {s.value: 0 for s in InstanceStatus}
    rows = (
        inst_query.with_entities(Instance.status, func.count(Instance.id))
        .group_by(Instance.status)
        .all()
    )
    for status, count in rows:
        status_counts[status.value] = count

    warning_count = inst_query.filter(
        Instance.cpuUsage >= settings.CPU_WARNING_THRESHOLD,
        Instance.status == InstanceStatus.RUNNING,
    ).count()

    total_cost = (
        inst_query.with_entities(func.coalesce(func.sum(Instance.monthlyCost), 0.0))
        .scalar()
    )

    # The count comes from the database and the list is capped. Taking the count as
    # `len(unresolved)` meant loading and serialising every unresolved alert a caller
    # could see just to report a number, on the fastest-growing table in the schema —
    # docs/performance/PERFORMANCE_BUGS.md § PERF-07. `unresolvedAlertCount` is still
    # the true total, so it can exceed the length of the embedded preview.
    unresolved_query = alert_query.filter(Alert.isResolved.is_(False))
    unresolved_count = (
        unresolved_query.with_entities(func.count(Alert.id)).scalar() or 0
    )
    unresolved = (
        unresolved_query.order_by(Alert.detectedAt.desc(), Alert.id.desc())
        .limit(REPORT_ALERT_LIMIT)
        .all()
    )

    return {
        "generatedAt": utcnow(),
        "instanceCountByStatus": status_counts,
        "warningCount": warning_count,
        "totalMonthlyCost": round(float(total_cost), 2),
        "unresolvedAlertCount": unresolved_count,
        "unresolvedAlerts": unresolved,
    }
