from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.controllers import (
    alert_controller,
    auth_controller,
    client_controller,
    instance_controller,
    monitor_controller,
)
from app.core.exceptions import (
    ActiveInstanceException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.database import Base, SessionLocal, engine
from app.seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # `create_all` skips a table that already exists — its indexes included — so a
    # database file created before an index was declared would never get it, and the
    # project has no migration step (docs/design/ERD.md § Known Gaps). Creating the
    # indexes separately with `checkfirst` is idempotent and covers both cases.
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            index.create(bind=engine, checkfirst=True)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Internal monitoring system for cloud instances across TechValley's client companies.\n\n"
        "**Demo accounts** (seeded on first run):\n"
        "- ADMIN: `admin@techvalley.vn` / `admin123!`\n"
        "- CLIENT_MANAGER: `lam@techvalley.vn` / `manager123!`\n"
        "- CLIENT_MANAGER: `minh@techvalley.vn` / `manager123!`\n\n"
        "Login via `POST /api/auth/login`, then click **Authorize** and paste the `accessToken`."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(ActiveInstanceException)
async def active_instance_handler(request: Request, exc: ActiveInstanceException):
    return JSONResponse(
        status_code=409,
        content={"error": "ActiveInstanceException", "detail": str(exc)},
    )


@app.exception_handler(NotFoundException)
async def not_found_handler(request: Request, exc: NotFoundException):
    return JSONResponse(status_code=404, content={"error": "NotFound", "detail": str(exc)})


@app.exception_handler(ForbiddenException)
async def forbidden_handler(request: Request, exc: ForbiddenException):
    return JSONResponse(status_code=403, content={"error": "Forbidden", "detail": exc.detail})


@app.exception_handler(ValidationException)
async def validation_handler(request: Request, exc: ValidationException):
    return JSONResponse(status_code=400, content={"error": "ValidationError", "detail": exc.detail})


app.include_router(auth_controller.router)
app.include_router(instance_controller.router)
app.include_router(monitor_controller.router)
app.include_router(alert_controller.router)
app.include_router(client_controller.router)


@app.get("/", tags=["Health"], summary="Health check")
def health():
    return {"status": "ok", "service": settings.APP_NAME, "docs": "/docs"}
