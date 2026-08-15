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
Full API table, business rules, and demo accounts: [README.md](README.md).
Data model: [docs/ERD.md](docs/ERD.md).

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
