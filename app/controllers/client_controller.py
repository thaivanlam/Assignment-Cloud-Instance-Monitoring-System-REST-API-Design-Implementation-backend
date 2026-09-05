from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import (
    accessible_client_ids,
    assert_client_access,
    get_current_member,
    require_admin,
)
from app.database import get_db
from app.models import Member
from app.pagination import DEFAULT_SIZE, PageParam, SizeParam
from app.schemas.schemas import (
    ClientCostResponse,
    ClientCreate,
    ClientOut,
    CostForecastResponse,
    InstanceOut,
    PageResponse,
    SlaResponse,
)
from app.services import client_service

router = APIRouter(prefix="/api/clients", tags=["Clients"])


@router.post("", response_model=ClientOut, status_code=201, summary="Register client (ADMIN only)")
def create_client(
    body: ClientCreate,
    db: Session = Depends(get_db),
    _admin: Member = Depends(require_admin),
):
    return client_service.create_client(db, body)


@router.get(
    "",
    response_model=PageResponse[ClientOut],
    summary="Get all clients (scoped by role, paginated)",
)
def list_clients(
    page: PageParam = 1,
    size: SizeParam = DEFAULT_SIZE,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    items, total, total_pages = client_service.list_clients(
        db, accessible_client_ids(member), page=page, size=size
    )
    return PageResponse(
        items=items, total=total, page=page, size=size, totalPages=total_pages
    )


@router.get(
    "/{client_id}/instances",
    response_model=PageResponse[InstanceOut],
    summary="Get instances by client (paginated)",
)
def client_instances(
    client_id: int,
    page: PageParam = 1,
    size: SizeParam = DEFAULT_SIZE,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    client = client_service.get_client(db, client_id)
    assert_client_access(member, client)
    items, total, total_pages = client_service.list_client_instances(
        db, client_id, page=page, size=size
    )
    return PageResponse(
        items=items, total=total, page=page, size=size, totalPages=total_pages
    )


@router.get("/{client_id}/cost", response_model=ClientCostResponse, summary="Monthly cost total by client")
def client_cost(
    client_id: int,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    client = client_service.get_client(db, client_id)
    assert_client_access(member, client)
    return client_service.get_client_cost(db, client_id)


@router.get(
    "/{client_id}/cost-forecast",
    response_model=CostForecastResponse,
    summary="Next month cost forecast (RUNNING instances x unit price)",
)
def client_cost_forecast(
    client_id: int,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    client = client_service.get_client(db, client_id)
    assert_client_access(member, client)
    return client_service.get_cost_forecast(db, client_id)


@router.get(
    "/{client_id}/sla",
    response_model=SlaResponse,
    summary="SLA uptime calculation (PREMIUM 99.9 / STANDARD 99 / BASIC 95)",
)
def client_sla(
    client_id: int,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    client = client_service.get_client(db, client_id)
    assert_client_access(member, client)
    return client_service.get_sla(db, client_id)
