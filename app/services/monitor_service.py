from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import func, insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Alert, AlertType, Instance, InstanceStatus
from app.models.models import utcnow

# The dedup probe reads every instance id of a scan in one statement. SQLite caps a
# statement at 32766 bind parameters, so the ids go in batches — one query per batch
# instead of one per instance, and never a statement that cannot be prepared.
ID_BATCH_SIZE = 500


def _instances_with_unresolved_alert(
    db: Session, instance_ids: list[int], alert_type: AlertType
) -> set[int]:
    """The subset of `instance_ids` that already carries an unresolved alert of this type."""
    found: set[int] = set()
    for start in range(0, len(instance_ids), ID_BATCH_SIZE):
        batch = instance_ids[start : start + ID_BATCH_SIZE]
        found.update(
            row[0]
            for row in db.query(Alert.instanceId).filter(
                Alert.instanceId.in_(batch),
                Alert.alertType == alert_type,
                Alert.isResolved.is_(False),
            )
        )
    return found


def _record_alerts(
    db: Session,
    instances: list[Instance],
    alert_type: AlertType,
    message: Callable[[Instance], str],
) -> bool:
    """Records one alert per instance that has no unresolved alert of this type yet.

    The dedup rule is unchanged (docs/business-rules/ALERTING.md § 3) — an instance with
    an open alert of the same type is still skipped. What changed is the number of
    statements: the whole scan is checked in one query rather than one per instance, and
    the new alerts are inserted as a batch. See docs/performance/PERFORMANCE_BUGS.md
    § PERF-05.

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


def _commit_if_recorded(db: Session, recorded: bool) -> None:
    """Commits a scan only when it actually opened a new alert.

    A scan that finds nothing new is a pure read, and committing one would still take
    SQLite's write lock and fsync — serialising every other request behind a dashboard
    poll that changed nothing. Dedup means most polls are exactly that case.
    """
    if recorded:
        db.commit()


def check_warnings(db: Session, client_ids: list[int] | None) -> list[Instance]:
    """CPU >= 80% instances; auto-records a CPU_HIGH alert for each (skip if
    an unresolved CPU_HIGH alert already exists)."""
    query = db.query(Instance).filter(
        Instance.cpuUsage >= settings.CPU_WARNING_THRESHOLD,
        Instance.status == InstanceStatus.RUNNING,
    )
    if client_ids is not None:
        query = query.filter(Instance.clientId.in_(client_ids or [-1]))
    instances = query.order_by(Instance.id).all()

    recorded = _record_alerts(
        db, instances, AlertType.CPU_HIGH,
        lambda inst: (
            f"CPU usage {inst.cpuUsage:.1f}% >= {settings.CPU_WARNING_THRESHOLD:.0f}% "
            f"on instance '{inst.instanceName}' ({inst.region})"
        ),
    )
    _commit_if_recorded(db, recorded)
    return instances


def check_errors(db: Session, client_ids: list[int] | None) -> list[Instance]:
    """ERROR status instances; auto-records a critical ERROR_DETECTED alert."""
    query = db.query(Instance).filter(Instance.status == InstanceStatus.ERROR)
    if client_ids is not None:
        query = query.filter(Instance.clientId.in_(client_ids or [-1]))
    instances = query.order_by(Instance.id).all()

    recorded = _record_alerts(
        db, instances, AlertType.ERROR_DETECTED,
        lambda inst: (
            f"[CRITICAL] Instance '{inst.instanceName}' ({inst.region}) is in ERROR state"
        ),
    )
    _commit_if_recorded(db, recorded)
    return instances


def check_long_stopped(db: Session, client_ids: list[int] | None) -> list[Instance]:
    """Instances STOPPED for 48+ hours (based on last status update time).
    Also records a LONG_STOPPED alert for visibility."""
    now = utcnow()
    threshold = now - timedelta(hours=settings.LONG_STOPPED_HOURS)
    query = db.query(Instance).filter(
        Instance.status == InstanceStatus.STOPPED,
        Instance.updatedAt <= threshold,
    )
    if client_ids is not None:
        query = query.filter(Instance.clientId.in_(client_ids or [-1]))
    instances = query.order_by(Instance.id).all()

    def stopped_message(inst: Instance) -> str:
        hours = (now - inst.updatedAt).total_seconds() / 3600
        return (
            f"Instance '{inst.instanceName}' has been STOPPED for {hours:.0f} hours "
            f"(>= {settings.LONG_STOPPED_HOURS}h)"
        )

    recorded = _record_alerts(db, instances, AlertType.LONG_STOPPED, stopped_message)
    _commit_if_recorded(db, recorded)
    return instances


def build_report(db: Session, client_ids: list[int] | None) -> dict:
    inst_query = db.query(Instance)
    alert_query = db.query(Alert).join(Instance, Alert.instanceId == Instance.id)
    if client_ids is not None:
        inst_query = inst_query.filter(Instance.clientId.in_(client_ids or [-1]))
        alert_query = alert_query.filter(Instance.clientId.in_(client_ids or [-1]))

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

    unresolved = alert_query.filter(Alert.isResolved.is_(False)).order_by(Alert.detectedAt.desc()).all()

    return {
        "generatedAt": utcnow(),
        "instanceCountByStatus": status_counts,
        "warningCount": warning_count,
        "totalMonthlyCost": round(float(total_cost), 2),
        "unresolvedAlertCount": len(unresolved),
        "unresolvedAlerts": unresolved,
    }
