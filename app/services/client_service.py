

from sqlalchemy.orm import Session

from app.config import SLA_THRESHOLDS, UNIT_PRICES
from app.core.exceptions import NotFoundException, ValidationException
from app.models import Client, Instance, InstanceStatus, Role
from app.models.models import utcnow
from app.schemas.schemas import ClientCreate


def create_client(db: Session, data: ClientCreate) -> Client:
    from app.models import Member

    manager = db.get(Member, data.managerId)
    if manager is None:
        raise NotFoundException("Member (manager)", data.managerId)
    if manager.role != Role.CLIENT_MANAGER:
        raise ValidationException(
            f"managerId {data.managerId} must belong to a CLIENT_MANAGER "
            f"(found role {manager.role.value})"
        )
    client = Client(
        clientName=data.clientName,
        contractPlan=data.contractPlan,
        managerId=data.managerId,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def list_clients(db: Session, client_ids: list[int] | None) -> list[Client]:
    query = db.query(Client)
    if client_ids is not None:
        query = query.filter(Client.id.in_(client_ids or [-1]))
    return query.order_by(Client.id).all()


def get_client(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise NotFoundException("Client", client_id)
    return client


def get_client_instances(db: Session, client_id: int) -> list[Instance]:
    get_client(db, client_id)
    return db.query(Instance).filter(Instance.clientId == client_id).order_by(Instance.id).all()


def get_client_cost(db: Session, client_id: int) -> dict:
    """Current-month total cost for a client, based on each instance's monthlyCost."""
    client = get_client(db, client_id)
    instances = get_client_instances(db, client_id)
    now = utcnow()
    return {
        "clientId": client.id,
        "clientName": client.clientName,
        "month": now.strftime("%Y-%m"),
        "instanceCount": len(instances),
        "totalMonthlyCost": round(sum(i.monthlyCost for i in instances), 2),
        "costByInstance": [
            {
                "instanceId": i.id,
                "instanceName": i.instanceName,
                "instanceType": i.instanceType.value,
                "status": i.status.value,
                "monthlyCost": i.monthlyCost,
            }
            for i in instances
        ],
    }


def get_cost_forecast(db: Session, client_id: int) -> dict:
    """Next-month forecast: unit price x count of currently RUNNING instances.
    SMALL $50 / MEDIUM $120 / LARGE $250 per month."""
    client = get_client(db, client_id)
    running = (
        db.query(Instance)
        .filter(Instance.clientId == client_id, Instance.status == InstanceStatus.RUNNING)
        .all()
    )

    breakdown: dict[str, dict] = {}
    total = 0.0
    for inst in running:
        t = inst.instanceType.value
        entry = breakdown.setdefault(t, {"count": 0, "unitPrice": UNIT_PRICES[t], "subtotal": 0.0})
        entry["count"] += 1
        entry["subtotal"] = round(entry["count"] * entry["unitPrice"], 2)
    total = round(sum(e["subtotal"] for e in breakdown.values()), 2)

    now = utcnow()
    next_month = (now.month % 12) + 1
    next_year = now.year + (1 if now.month == 12 else 0)

    return {
        "clientId": client.id,
        "clientName": client.clientName,
        "forecastMonth": f"{next_year:04d}-{next_month:02d}",
        "runningInstanceCount": len(running),
        "forecastCost": total,
        "breakdown": breakdown,
    }


def get_sla(db: Session, client_id: int) -> dict:
    """SLA uptime for the current month.

    Approximation (no status-history table in the schema): an instance counts as
    "up" from max(month start, launchedAt) until now if RUNNING, or until its
    last status change (updatedAt) if currently STOPPED/ERROR. The client uptime
    is the average across its instances, compared against the contract plan
    threshold (PREMIUM 99.9 / STANDARD 99 / BASIC 95).
    """
    client = get_client(db, client_id)
    instances = get_client_instances(db, client_id)

    now = utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    threshold = SLA_THRESHOLDS[client.contractPlan.value]

    details = []
    percents = []
    for inst in instances:
        window_start = max(month_start, inst.launchedAt)
        total_hours = (now - window_start).total_seconds() / 3600
        if total_hours <= 0:
            continue

        if inst.status == InstanceStatus.RUNNING:
            up_end = now
        else:
            up_end = min(max(inst.updatedAt, window_start), now)
        up_hours = max((up_end - window_start).total_seconds() / 3600, 0.0)

        pct = round(min(up_hours / total_hours, 1.0) * 100, 3)
        percents.append(pct)
        details.append(
            {
                "instanceId": inst.id,
                "instanceName": inst.instanceName,
                "status": inst.status.value,
                "measuredHours": round(total_hours, 1),
                "runningHours": round(up_hours, 1),
                "uptimePercent": pct,
            }
        )

    uptime = round(sum(percents) / len(percents), 3) if percents else 100.0

    return {
        "clientId": client.id,
        "clientName": client.clientName,
        "contractPlan": client.contractPlan,
        "slaThreshold": threshold,
        "month": now.strftime("%Y-%m"),
        "uptimePercent": uptime,
        "isViolation": uptime < threshold,
        "instanceDetails": details,
    }
