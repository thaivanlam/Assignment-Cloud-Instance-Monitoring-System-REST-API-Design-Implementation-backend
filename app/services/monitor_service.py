from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Alert, AlertType, Instance, InstanceStatus
from app.models.models import utcnow


def _has_unresolved_alert(db: Session, instance_id: int, alert_type: AlertType) -> bool:
    return (
        db.query(Alert)
        .filter(
            Alert.instanceId == instance_id,
            Alert.alertType == alert_type,
            Alert.isResolved.is_(False),
        )
        .first()
        is not None
    )


def _record_alert(db: Session, instance: Instance, alert_type: AlertType, message: str) -> bool:
    """Records an alert unless an unresolved one of the same type already exists.
    Returns True if a new alert was created."""
    if _has_unresolved_alert(db, instance.id, alert_type):
        return False
    db.add(Alert(instanceId=instance.id, alertType=alert_type, message=message))
    return True


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

    for inst in instances:
        _record_alert(
            db, inst, AlertType.CPU_HIGH,
            f"CPU usage {inst.cpuUsage:.1f}% >= {settings.CPU_WARNING_THRESHOLD:.0f}% "
            f"on instance '{inst.instanceName}' ({inst.region})",
        )
    db.commit()
    return instances


def check_errors(db: Session, client_ids: list[int] | None) -> list[Instance]:
    """ERROR status instances; auto-records a critical ERROR_DETECTED alert."""
    query = db.query(Instance).filter(Instance.status == InstanceStatus.ERROR)
    if client_ids is not None:
        query = query.filter(Instance.clientId.in_(client_ids or [-1]))
    instances = query.order_by(Instance.id).all()

    for inst in instances:
        _record_alert(
            db, inst, AlertType.ERROR_DETECTED,
            f"[CRITICAL] Instance '{inst.instanceName}' ({inst.region}) is in ERROR state",
        )
    db.commit()
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

    for inst in instances:
        hours = (now - inst.updatedAt).total_seconds() / 3600
        _record_alert(
            db, inst, AlertType.LONG_STOPPED,
            f"Instance '{inst.instanceName}' has been STOPPED for {hours:.0f} hours "
            f"(>= {settings.LONG_STOPPED_HOURS}h)",
        )
    db.commit()
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
