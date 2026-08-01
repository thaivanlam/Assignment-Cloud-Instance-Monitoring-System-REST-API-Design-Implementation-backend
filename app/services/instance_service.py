from datetime import datetime

from sqlalchemy.orm import Session

from app.config import UNIT_PRICES
from app.core.exceptions import ActiveInstanceException, NotFoundException
from app.models import Client, Instance, InstanceStatus
from app.models.models import utcnow
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
    size: int = 10,
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

    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    total_pages = (total + size - 1) // size if size else 0
    return items, total, total_pages


def get_instance(db: Session, instance_id: int) -> Instance:
    instance = db.get(Instance, instance_id)
    if instance is None:
        raise NotFoundException("Instance", instance_id)
    return instance


def update_status(db: Session, instance_id: int, data: InstanceStatusUpdate) -> Instance:
    instance = get_instance(db, instance_id)
    instance.status = data.status
    if data.cpuUsage is not None:
        instance.cpuUsage = data.cpuUsage
    elif data.status != InstanceStatus.RUNNING:
        instance.cpuUsage = 0.0
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
