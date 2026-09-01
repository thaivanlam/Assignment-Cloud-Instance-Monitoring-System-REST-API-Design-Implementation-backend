from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import accessible_client_ids, get_current_member
from app.database import get_db
from app.models import Member
from app.pagination import DEFAULT_SIZE, PageParam, SizeParam
from app.schemas.schemas import InstanceOut, MonitorReport, PageResponse
from app.services import monitor_service

router = APIRouter(prefix="/api/monitor", tags=["Monitoring"])


@router.get(
    "/warnings",
    response_model=PageResponse[InstanceOut],
    summary="CPU >= 80% list + auto-record Alert (skips if unresolved alert exists)",
)
def warnings(
    page: PageParam = 1,
    size: SizeParam = DEFAULT_SIZE,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    items, total, total_pages = monitor_service.check_warnings(
        db, accessible_client_ids(member, db), page=page, size=size
    )
    return PageResponse(
        items=items, total=total, page=page, size=size, totalPages=total_pages
    )


@router.get(
    "/errors",
    response_model=PageResponse[InstanceOut],
    summary="ERROR status list + auto-record critical Alert",
)
def errors(
    page: PageParam = 1,
    size: SizeParam = DEFAULT_SIZE,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    items, total, total_pages = monitor_service.check_errors(
        db, accessible_client_ids(member, db), page=page, size=size
    )
    return PageResponse(
        items=items, total=total, page=page, size=size, totalPages=total_pages
    )


@router.get(
    "/long-stopped",
    response_model=PageResponse[InstanceOut],
    summary="Instances STOPPED for 48+ hours",
)
def long_stopped(
    page: PageParam = 1,
    size: SizeParam = DEFAULT_SIZE,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    items, total, total_pages = monitor_service.check_long_stopped(
        db, accessible_client_ids(member, db), page=page, size=size
    )
    return PageResponse(
        items=items, total=total, page=page, size=size, totalPages=total_pages
    )


@router.get(
    "/report",
    response_model=MonitorReport,
    summary="Full status report (count by status / warnings / total cost / unresolved alerts)",
)
def report(db: Session = Depends(get_db), member: Member = Depends(get_current_member)):
    return monitor_service.build_report(db, accessible_client_ids(member, db))
