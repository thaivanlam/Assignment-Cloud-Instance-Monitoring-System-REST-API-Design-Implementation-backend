from datetime import datetime

from sqlalchemy.orm import Session

from app.config import UNIT_PRICES
from app.core.exceptions import ActiveInstanceException, NotFoundException
from app.models import Client, Instance, InstanceStatus
from app.models.models import utcnow
from app.pagination import DEFAULT_SIZE, paginate
from app.schemas.schemas import InstanceCreate, InstanceStatusUpdate

SORTABLE_FIELDS = {
    "id", "instanceName", "region", "instanceType", "status",
    "cpuUsage", "monthlyCost", "clientId", "launchedAt", "updatedAt",
}


def create_instance(db: Session, data: InstanceCreate) -> Instance:
    client = db.get(Client, data.clientId)
    if client is None:
        raise NotFoundException("Client", data.clientId)

    instance = Instance(
        instanceName=data.instanceName,
        region=data.region,
        instanceType=data.instanceType,
        status=data.status,
        cpuUsage=data.cpuUsage,
        monthlyCost=UNIT_PRICES[data.instanceType.value],
        clientId=data.clientId,
        launchedAt=utcnow(),
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


def list_instances(
    db: Session,
    client_ids: list[int] | None,
    page: int = 1,
    size: int = DEFAULT_SIZE,
    status: InstanceStatus | None = None,
    clientId: int | None = None,
    region: str | None = None,
    instanceType: str | None = None,
    sort: str = "id",
):
    query = db.query(Instance)

    # Role-based visibility: CLIENT_MANAGER only sees their clients' instances
    if client_ids is not None:
        query = query.filter(Instance.clientId.in_(client_ids or [-1]))

    if status is not None:
        query = query.filter(Instance.status == status)
    if clientId is not None:
        query = query.filter(Instance.clientId == clientId)
    if region is not None:
        query = query.filter(Instance.region == region)
    if instanceType is not None:
        query = query.filter(Instance.instanceType == instanceType)

    # Sorting: "field" ascending, "-field" descending
    descending = sort.startswith("-")
    field = sort.lstrip("-")
    if field not in SORTABLE_FIELDS:
        field = "id"
    column = getattr(Instance, field)
    query = query.order_by(column.desc() if descending else column.asc())
    # `id` last, to break ties on the sort key. Most sortable fields are not unique —
    # `status`, `region`, `instanceType` least of all — and rows tied on the sort key
    # have no defined order between them, so a row could otherwise appear on two pages
    # or on none as the caller walks them.
    if field != "id":
        query = query.order_by(Instance.id.asc())

    return paginate(query, Instance.id, page, size)


def get_instance(db: Session, instance_id: int) -> Instance:
    instance = db.get(Instance, instance_id)
    if instance is None:
        raise NotFoundException("Instance", instance_id)
    return instance


def update_status(db: Session, instance_id: int, data: InstanceStatusUpdate) -> Instance:
    instance = get_instance(db, instance_id)

    # Treat an identical PATCH as a no-op.  This matters because the monitoring
    # module uses updatedAt as the best available "status changed at" value for
    # the 48-hour STOPPED rule.  Repeating the same request must not restart that
    # clock.
    next_cpu_usage = data.cpuUsage
    if next_cpu_usage is None and data.status != InstanceStatus.RUNNING:
        next_cpu_usage = 0.0

    status_changed = instance.status != data.status
    cpu_changed = next_cpu_usage is not None and instance.cpuUsage != next_cpu_usage
    if not status_changed and not cpu_changed:
        return instance

    instance.status = data.status
    if next_cpu_usage is not None:
        instance.cpuUsage = next_cpu_usage
    instance.updatedAt = utcnow()
    db.commit()
    db.refresh(instance)
    return instance


def delete_instance(db: Session, instance_id: int) -> None:
    instance = get_instance(db, instance_id)
    if instance.status == InstanceStatus.RUNNING:
        raise ActiveInstanceException(instance_id)
    db.delete(instance)
    db.commit()
