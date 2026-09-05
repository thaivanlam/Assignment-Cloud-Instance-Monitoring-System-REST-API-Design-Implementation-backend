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
├── database.py              SQLAlchemy engine, pool sizing, SQLite pragmas, SessionLocal, get_db
├── pagination.py            The page/size query pair and the counting behind PageResponse
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

[app/pagination.py](../../app/pagination.py) sits outside the table above because it
straddles two of its rows deliberately: it declares the `page` and `size` query
parameters that controllers bind, and the `paginate()` helper that services call. Putting
either half in the other layer would mean the bounds and the counting drifting apart
across the seven endpoints that share them. It is a convention rather than a rule —
nothing in it is specific to instances, alerts or clients — and the convention itself is
[../api/CONVENTIONS.md § 1](../api/CONVENTIONS.md#1-pagination).

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
     │      or, when only the id is in hand
     ├─ assert_client_id_access(db, member, id)   → 403 if out of scope, as one EXISTS
     │      or, for a list
     └─ accessible_client_ids(member)             → None (ADMIN) or an id subquery
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

Every list endpoint returns `(items, total, totalPages)` from its service and the
controller wraps that in `PageResponse`. The service decides *what* the page is, because
scoping and filtering decide what `total` counts; the controller only echoes back the
`page` and `size` it was given.

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
| [monitor_service.py](../../app/services/monitor_service.py) | Detection thresholds, alert auto-recording and dedup, the batched scan walk, the report |
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
2. `index.create(bind=engine, checkfirst=True)` for every index in the metadata — creates
   any missing index. `create_all` skips a table that already exists and its indexes with
   it, so this second pass is what lets an index be added to a database file that predates
   it. It is idempotent: on a file that already has them all it issues no `CREATE`.
3. `seed(db)` — populates demo data, returning immediately if a member already exists.

There are no migrations. The schema is created from the ORM models, which is adequate
for an assignment with a disposable SQLite file but would need Alembic for anything
longer-lived — a column change today means deleting `monitoring.db`. Step 2 is the narrow
exception: indexes, which are additive and safe to create against live data, do reach an
existing file. Which columns are indexed and why: [ERD.md § Indexes](ERD.md#indexes).

### SQLite connection settings

When `DATABASE_URL` names SQLite, `_set_sqlite_pragmas`
([app/database.py](../../app/database.py)) runs on every new connection and sets
`journal_mode=WAL` and `synchronous=NORMAL`. The default rollback journal locks the entire
database file for the length of a write, which the monitoring scans — `GET`s that record
alerts — turn into a lock every dashboard poll had to queue behind. WAL lets readers work
from the last committed snapshot while a writer runs. WAL keeps two sidecar files,
`monitoring.db-wal` and `monitoring.db-shm`, next to the database; both are ignored by git.
The hook is skipped entirely for a non-SQLite `DATABASE_URL`. Background:
[../performance/PERFORMANCE_BUGS.md § PERF-01](../performance/PERFORMANCE_BUGS.md#perf-01).

### Connection pool

Every controller is declared `def`, so FastAPI runs it in AnyIO's worker threadpool, which
allows 40 workers at once — and `get_db` holds one connection for the whole request. The
engine is sized to match ([app/database.py](../../app/database.py)):

```python
MAX_CONCURRENT_REQUESTS = 40          # AnyIO's default threadpool limit
POOL_SIZE = 20                        # kept open
MAX_OVERFLOW = 20                     # opened on demand
```

20 + 20 = 40 connections, so 40 concurrent handlers each find one. On SQLAlchemy's
defaults (5 + 10 = 15) the surplus requests queued in `pool.connect()` and failed with a
500 once the 30-second pool timeout expired. `pool_pre_ping=True` replaces a connection the
other end has closed rather than failing the request that borrowed it. The sizing is
skipped for an in-memory SQLite URL, which gets a `SingletonThreadPool` that has no
overflow to size. Background:
[../performance/PERFORMANCE_BUGS.md § PERF-02](../performance/PERFORMANCE_BUGS.md#perf-02).

One handler ends its session early on purpose. `GET /api/instances/{id}/diagnosis`
waits on a third-party API, and `get_db` would otherwise keep its connection checked
out for that whole wait, so the controller calls `db.close()` once it has loaded
everything the response needs and before it calls the provider — 20 concurrent
diagnoses held 20 connections before, and hold none now. `Session.close()` resets the
session rather than tearing it down, so `get_db` closing it again is a no-op, and the
rows it loaded stay readable because closing detaches without expiring. Background:
[../performance/PERFORMANCE_BUGS.md § PERF-03](../performance/PERFORMANCE_BUGS.md#perf-03);
the rule that keeps it safe is in
[LLM_FEATURE.md § 4.5](LLM_FEATURE.md#45-request-limits-and-the-database-connection).

Which pool class each `DATABASE_URL` gets, and why the in-memory mode belongs to the tests
alone: [DATABASE.md](DATABASE.md).

### The session factory

`SessionLocal` is built with `expire_on_commit=False`
([app/database.py](../../app/database.py)), so the rows a request has already loaded stay
readable after it commits. On SQLAlchemy's default every `commit()` marks every loaded
object expired, and the next attribute read re-fetches it — which is exactly what the
monitoring scans do: they commit the alerts they recorded and then hand the instances they
scanned to Pydantic, so serialising the response issued one `SELECT` per row returned. An
`ADMIN` warnings scan cost 8 statements for 4 rows; it costs 4 now, and the count no
longer grows with the result set.

Nothing depends on the expiry it removes. The four functions that want post-commit state
— `create_instance`, `update_status`, `create_client` and `resolve_alert` — call
`db.refresh()` explicitly, and each still issues exactly the one `SELECT` it did before.
Sessions are per-request (`get_db` opens one and closes it after the response), so a
retained value never outlives the request that loaded it. Background:
[../performance/PERFORMANCE_BUGS.md § PERF-06](../performance/PERFORMANCE_BUGS.md#perf-06).

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
| [DATABASE.md](DATABASE.md) | Engine and pool selection, and the in-memory SQLite mode |
| [LLM_FEATURE.md](LLM_FEATURE.md) | The one service with an external dependency |
| [../business-rules/](../business-rules/README.md) | What lives in the service layer |
| [../api/](../api/README.md) | What the controllers expose |
