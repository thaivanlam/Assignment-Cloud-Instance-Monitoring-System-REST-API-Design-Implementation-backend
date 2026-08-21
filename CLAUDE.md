# CLAUDE.md

## Project

TechValley cloud instance monitoring REST API — FastAPI + SQLAlchemy (SQLite),
Pydantic v2, PyJWT auth, Anthropic SDK for the LLM diagnosis endpoint.

MVC layout under `app/`:

| Dir | Role |
|---|---|
| `models/` | SQLAlchemy 2.0 ORM entities |
| `schemas/` | Pydantic v2 request/response DTOs |
| `controllers/` | APIRouter endpoints |
| `services/` | Business logic (monitoring, alerts, cost, SLA, LLM) |
| `core/` | JWT security, auth dependencies, domain exceptions |

```bash
uvicorn app.main:app --reload   # run (Swagger at /docs)
pytest -q                       # tests
```

`monitoring.db` is created and seeded automatically on startup by `app/seed.py`.

## Documentation rules

These apply to every change in this repository, for every contributor.

1. **English only.** All documentation is written in English regardless of the language
   used in discussion, issues, or commit messages.
2. **Read the relevant document first.** Before changing code in an area, read the
   document that describes it — use the mapping below.
3. **Code and docs change together.** When behaviour changes, update the corresponding
   document in the *same commit*. A behaviour change with a stale document is an
   incomplete change.
4. **Every `docs/` folder has a `README.md`** that links to the files inside it and to
   related documents elsewhere. When adding a document, add its link to that README, to
   [docs/README.md](docs/README.md), and to the direct-links table in
   [README.md](README.md).

### Source → document mapping

| When you change… | Update… |
|---|---|
| `app/controllers/**` — routes, params, status codes | [docs/api/ENDPOINTS.md](docs/api/ENDPOINTS.md), [docs/api/OVERVIEW.md](docs/api/OVERVIEW.md) |
| `app/schemas/**` — request/response fields | [docs/api/ENDPOINTS.md](docs/api/ENDPOINTS.md) |
| `app/models/**` — tables, columns, relationships | [docs/design/ERD.md](docs/design/ERD.md) |
| `app/services/instance_service.py` | [docs/business-rules/INSTANCE_LIFECYCLE.md](docs/business-rules/INSTANCE_LIFECYCLE.md) |
| `app/services/monitor_service.py`, `alert_service.py` | [docs/business-rules/ALERTING.md](docs/business-rules/ALERTING.md) |
| `app/services/client_service.py` — cost | [docs/business-rules/COST.md](docs/business-rules/COST.md) |
| `app/services/client_service.py` — SLA | [docs/business-rules/SLA.md](docs/business-rules/SLA.md) |
| `app/services/llm_service.py` | [docs/design/LLM_FEATURE.md](docs/design/LLM_FEATURE.md) |
| `app/core/**` — auth, deps, exceptions | [docs/api/AUTHENTICATION.md](docs/api/AUTHENTICATION.md), [docs/business-rules/AUTHORIZATION.md](docs/business-rules/AUTHORIZATION.md), [docs/api/ERRORS.md](docs/api/ERRORS.md) |
| `app/config.py` — thresholds, pricing | [docs/business-rules/README.md](docs/business-rules/README.md), [docs/design/ARCHITECTURE.md](docs/design/ARCHITECTURE.md) |
| `app/seed.py` — demo data | [docs/demo/SEED_DATA.md](docs/demo/SEED_DATA.md), [docs/demo/ACCOUNTS.md](docs/demo/ACCOUNTS.md) |
| `app/main.py` — routers, handlers, startup | [docs/design/ARCHITECTURE.md](docs/design/ARCHITECTURE.md), [docs/api/ERRORS.md](docs/api/ERRORS.md) |
| Project layout or new module | [docs/design/ARCHITECTURE.md](docs/design/ARCHITECTURE.md) |

A change that alters observable behaviour also belongs in
[docs/demo/WALKTHROUGH.md](docs/demo/WALKTHROUGH.md) if it invalidates a step or an
expected number there.

Documentation index: [docs/README.md](docs/README.md).

## Commit conventions

Prefix every commit subject with its type:

| Prefix | Use for |
|---|---|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation |
| `refactor:` | Code refactoring |
| `test:` | Test code |

A change that alters behaviour *and* its document is one `feat:` or `fix:` commit
covering both — the documentation rule above requires them to land together, so do not
split the doc update into a separate `docs:` commit. Use `docs:` only when nothing
outside `docs/`, `README.md`, or `CLAUDE.md` changes.

## Reference docs — fetch on demand

**FastAPI: https://fastapi.tiangolo.com/**

Before writing or changing FastAPI code, WebFetch the relevant page instead of
answering from memory. Start narrow — fetch the specific page, not the index:

- `/tutorial/` — core usage
- `/tutorial/dependencies/` — `Depends`, our auth pattern in `app/core/`
- `/tutorial/sql-databases/` — session handling with SQLAlchemy
- `/tutorial/handling-errors/` — exception handlers, used in `app/main.py`
- `/advanced/` — background tasks, custom responses, middleware
- `/reference/` — API reference for exact signatures

Secondary, same rule (fetch the page, don't guess):

- Pydantic v2: https://docs.pydantic.dev/latest/
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/en/20/
