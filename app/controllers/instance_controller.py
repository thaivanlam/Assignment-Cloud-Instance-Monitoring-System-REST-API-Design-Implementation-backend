from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import accessible_client_ids, assert_client_access, get_current_member
from app.database import get_db
from app.models import Alert, InstanceStatus, InstanceType, Member
from app.pagination import DEFAULT_SIZE, PageParam, SizeParam
from app.schemas.schemas import (
    DiagnosisResponse,
    InstanceCreate,
    InstanceOut,
    InstanceStatusUpdate,
    PageResponse,
)
from app.services import instance_service, llm_service

router = APIRouter(prefix="/api/instances", tags=["Instances"])


@router.post("", response_model=InstanceOut, status_code=201, summary="Register instance")
def create_instance(
    body: InstanceCreate,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    from app.services.client_service import get_client

    client = get_client(db, body.clientId)
    assert_client_access(member, client)
    return instance_service.create_instance(db, body)


@router.get(
    "",
    response_model=PageResponse[InstanceOut],
    summary="Get all instances (pagination / filter / sort)",
)
def list_instances(
    page: PageParam = 1,
    size: SizeParam = DEFAULT_SIZE,
    status: InstanceStatus | None = Query(None, description="Filter by status"),
    clientId: int | None = Query(None, description="Filter by client"),
    region: str | None = Query(None, description="Filter by region"),
    instanceType: InstanceType | None = Query(None, description="Filter by type"),
    sort: str = Query("id", description="Sort field; prefix with '-' for descending (e.g. -cpuUsage)"),
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    client_ids = accessible_client_ids(member)
    items, total, total_pages = instance_service.list_instances(
        db, client_ids, page=page, size=size, status=status, clientId=clientId,
        region=region, instanceType=instanceType.value if instanceType else None, sort=sort,
    )
    return PageResponse(items=items, total=total, page=page, size=size, totalPages=total_pages)


@router.get("/{instance_id}", response_model=InstanceOut, summary="Get single instance")
def get_instance(
    instance_id: int,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    instance = instance_service.get_instance(db, instance_id)
    assert_client_access(member, instance.client)
    return instance


@router.patch(
    "/{instance_id}/status",
    response_model=InstanceOut,
    summary="Update instance status and optional CPU usage",
)
def update_status(
    instance_id: int,
    body: InstanceStatusUpdate,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    instance = instance_service.get_instance(db, instance_id)
    assert_client_access(member, instance.client)
    return instance_service.update_status(db, instance_id, body)


@router.delete(
    "/{instance_id}",
    status_code=204,
    summary="Delete instance (RUNNING -> 409 ActiveInstanceException)",
)
def delete_instance(
    instance_id: int,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    instance = instance_service.get_instance(db, instance_id)
    assert_client_access(member, instance.client)
    instance_service.delete_instance(db, instance_id)


@router.get(
    "/{instance_id}/diagnosis",
    response_model=DiagnosisResponse,
    summary="[LLM] Auto-generate cause & action for ERROR instance",
)
def diagnose_instance(
    instance_id: int,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    instance = instance_service.get_instance(db, instance_id)
    assert_client_access(member, instance.client)

    alerts = (
        db.query(Alert)
        .filter(Alert.instanceId == instance_id)
        .order_by(Alert.detectedAt.desc())
        .limit(10)
        .all()
    )
    # Every field the diagnosis and the response below need is loaded by now, so hand
    # the connection back before the provider call rather than after it. `get_db` keeps
    # its session — and therefore its pooled connection — checked out for the whole
    # request, and this is the one handler that spends most of its time on the network:
    # 40 concurrent diagnoses would otherwise empty the pool for every other endpoint.
    # `close()` resets the session and detaches the rows it loaded without expiring them,
    # so their values stay readable and the `get_db` close in `finally` is a no-op.
    # See docs/performance/PERFORMANCE_BUGS.md § PERF-03.
    db.close()

    diagnosis, source = llm_service.diagnose(instance, alerts)
    return DiagnosisResponse(
        instanceId=instance.id,
        instanceName=instance.instanceName,
        status=instance.status,
        diagnosis=diagnosis,
        source=source,
    )
