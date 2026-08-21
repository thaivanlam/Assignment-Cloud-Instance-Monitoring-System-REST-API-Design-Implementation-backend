# Architecture

MVC layering, request flow, and where each kind of logic belongs.

**Stack:** Python · FastAPI · SQLAlchemy 2.0 (SQLite) · Pydantic v2 · PyJWT ·
Anthropic SDK

---

## 1. Layout

```
app/
├── main.py                  FastAPI app, router registration, exception handlers, startup seed
├── config.py                Settings, unit pricing, SLA thresholds
├── database.py              SQLAlchemy engine, SessionLocal, get_db dependency
├── seed.py                  Idempotent demo data
├── models/                  M — SQLAlchemy ORM entities
├── schemas/                 V — Pydantic request/response DTOs
├── controllers/             C — APIRouter endpoints
├── services/                Business logic
└── core/                    JWT security, auth dependencies, domain exceptions
```

| Directory | Responsibility | Must not |
|---|---|---|
| `models/` | Table definitions, enums, relationships, `utcnow()` | Contain business rules |
| `schemas/` | Request validation and response serialisation | Touch the database |
| `controllers/` | Routing, dependency wiring, access assertions | Contain calculations or queries beyond trivial lookups |
| `services/` | Every rule, threshold, and query | Import FastAPI or raise `HTTPException` for domain failures |
| `core/` | JWT issue/verify, auth dependencies, domain exception types | Contain feature logic |

The boundary that matters most: **services raise domain exceptions, not HTTP errors.**
`NotFoundException`, `ActiveInstanceException`, and `ValidationException` are plain
Python exceptions ([app/core/exceptions.py](../../app/core/exceptions.py)) translated to
status codes by handlers registered in [app/main.py](../../app/main.py). That keeps the
service layer testable without a web client and keeps HTTP vocabulary out of the domain.

The exception is `app/core/deps.py`, which raises `HTTPException` directly — it is
already an HTTP-layer concern, so there is nothing to decouple.

---

## 2. Request flow

```
HTTP request
     │
     ▼
APIRouter endpoint  (app/controllers/…)
     │  Depends(get_db)              → SQLAlchemy Session, closed after the response
     │  Depends(get_current_member)  → decode JWT, load Member, or 401
     │  Depends(require_admin)       → ADMIN-only endpoints
     │
     ├─ load the resource via a service
     ├─ assert_client_access(member, client)      → 403 if out of scope
     │      or
     └─ accessible_client_ids(member, db)         → None (ADMIN) or id list (manager)
     │
     ▼
Service function  (app/services/…)
     │  applies business rules, queries and commits
     │  raises domain exceptions on rule violations
     ▼
Pydantic schema  (from_attributes=True)
     │
     ▼
JSON response  —  or an exception handler → { error, detail }
```

Role scoping is applied two different ways depending on the endpoint shape — filter-at-
query for lists, check-after-load for single resources. Both are described in
[../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md).

---

## 3. Controllers

| Module | Prefix | Tag |
|---|---|---|
| [auth_controller.py](../../app/controllers/auth_controller.py) | `/api/auth` | Auth |
| [instance_controller.py](../../app/controllers/instance_controller.py) | `/api/instances` | Instances |
| [monitor_controller.py](../../app/controllers/monitor_controller.py) | `/api/monitor` | Monitoring |
| [alert_controller.py](../../app/controllers/alert_controller.py) | `/api/alerts` | Alerts |
| [client_controller.py](../../app/controllers/client_controller.py) | `/api/clients` | Clients |

Tags group the endpoints in Swagger UI. Each router carries its own `prefix`, so paths
are declared once.

---

## 4. Services

| Module | Owns |
|---|---|
| [instance_service.py](../../app/services/instance_service.py) | Registration, listing/filter/sort, status transitions, deletion guard |
| [monitor_service.py](../../app/services/monitor_service.py) | Detection thresholds, alert auto-recording and dedup, the report |
| [alert_service.py](../../app/services/alert_service.py) | Alert history filtering, resolution |
| [client_service.py](../../app/services/client_service.py) | Client CRUD, cost, forecast, SLA |
| [llm_service.py](../../app/services/llm_service.py) | Anthropic call, prompt construction, rule-based fallback |

`llm_service` is fully isolated: the controller never imports `anthropic` and only
receives `(text, source)`. Swapping provider or prompt touches nothing else. See
[LLM_FEATURE.md](LLM_FEATURE.md).

---

## 5. Startup

`lifespan()` in [app/main.py](../../app/main.py) runs on boot:

1. `Base.metadata.create_all(bind=engine)` — creates any missing tables.
2. `seed(db)` — populates demo data, returning immediately if a member already exists.

There are no migrations. The schema is created from the ORM models, which is adequate
for an assignment with a disposable SQLite file but would need Alembic for anything
longer-lived — a column change today means deleting `monitoring.db`.

---

## 6. Configuration

All settings are Pydantic `BaseSettings` fields in
[app/config.py](../../app/config.py), read from `.env` with working defaults so the app
runs with no configuration at all.

| Setting | Default | Used by |
|---|---|---|
| `SECRET_KEY` | placeholder | JWT signing — **must be changed for any real deployment** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `120` | Token lifetime |
| `DATABASE_URL` | `sqlite:///./monitoring.db` | Engine |
| `ANTHROPIC_API_KEY` | `""` | LLM path; empty is a supported configuration |
| `CPU_WARNING_THRESHOLD` | `80.0` | Warning detection |
| `LONG_STOPPED_HOURS` | `48` | Long-stopped detection |
| `PRICE_SMALL/MEDIUM/LARGE` | `50` / `120` / `250` | Unit pricing |
| `SLA_PREMIUM/STANDARD/BASIC` | `99.9` / `99.0` / `95.0` | SLA thresholds |

`UNIT_PRICES` and `SLA_THRESHOLDS` are module-level dicts built from those fields, so
services look prices up by enum value without re-reading settings.

Note that the defaults are resolved **at import time**. Changing `.env` requires a
restart, and the derived dicts will not pick up a runtime mutation of `settings`.

---

## 7. Related

| Document | Why |
|---|---|
| [ERD.md](ERD.md) | The tables the models define |
| [LLM_FEATURE.md](LLM_FEATURE.md) | The one service with an external dependency |
| [../business-rules/](../business-rules/README.md) | What lives in the service layer |
| [../api/](../api/README.md) | What the controllers expose |
