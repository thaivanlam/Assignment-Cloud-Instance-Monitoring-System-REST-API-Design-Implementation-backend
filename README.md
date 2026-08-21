# TechValley — Cloud Instance Monitoring System

Internal monitoring system replacing manual Excel tracking of cloud instances for 10
client companies. Built for the TechValley Developer Track assignment.

**Stack:** Python · FastAPI · SQLAlchemy (SQLite) · Pydantic v2 · JWT (PyJWT) ·
Swagger/OpenAPI · Anthropic Claude (LLM diagnosis)
**Architecture:** MVC — `models/` (data), `schemas/` (DTO), `controllers/` (routing),
`services/` (business logic)

---

## Quick Start

```bash
# 1. Create a virtualenv and install dependencies
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

# 2. (Optional) configure — defaults work out of the box
copy .env.example .env

# 3. Run
uvicorn app.main:app --reload
```

- Swagger UI: **http://127.0.0.1:8000/docs**
- `monitoring.db` is created and **seeded automatically** on first run — 3 members,
  10 clients, 15 instances, cost snapshots.
- Log in with `admin@techvalley.vn` / `admin123!`, then follow
  [docs/demo/WALKTHROUGH.md](docs/demo/WALKTHROUGH.md).

```bash
# Tests
pip install -r requirements-dev.txt
pytest -q
```

---

## Documentation

Full documentation lives in **[docs/](docs/README.md)**. Each folder has its own README
linking to the files inside it.

| Folder | Contents |
|---|---|
| [docs/api/](docs/api/README.md) | Overview, authentication, request conventions, errors, per-endpoint reference |
| [docs/business-rules/](docs/business-rules/README.md) | Authorization, instance lifecycle, alerting, cost, SLA |
| [docs/demo/](docs/demo/README.md) | Demo accounts, seed data, step-by-step walkthrough |
| [docs/design/](docs/design/README.md) | Architecture, ERD, LLM feature design |
| [docs/team/](docs/team/README.md) | Per-member assignment scope |
| [docs/contributing/](docs/contributing/README.md) | Commit conventions and documentation rules |
| [docs/screenshots/](docs/screenshots/README.md) | Captured Swagger UI responses |

### Direct links

| Topic | Document |
|---|---|
| API endpoint reference | [docs/api/ENDPOINTS.md](docs/api/ENDPOINTS.md) |
| Authentication and JWT | [docs/api/AUTHENTICATION.md](docs/api/AUTHENTICATION.md) |
| Pagination, filtering, sorting | [docs/api/CONVENTIONS.md](docs/api/CONVENTIONS.md) |
| Status codes and error bodies | [docs/api/ERRORS.md](docs/api/ERRORS.md) |
| Business rules | [docs/business-rules/README.md](docs/business-rules/README.md) |
| Demo accounts | [docs/demo/ACCOUNTS.md](docs/demo/ACCOUNTS.md) |
| Demo walkthrough | [docs/demo/WALKTHROUGH.md](docs/demo/WALKTHROUGH.md) |
| Data model (ERD) | [docs/design/ERD.md](docs/design/ERD.md) |
| Architecture | [docs/design/ARCHITECTURE.md](docs/design/ARCHITECTURE.md) |
| LLM diagnosis feature | [docs/design/LLM_FEATURE.md](docs/design/LLM_FEATURE.md) |
| Commit conventions | [docs/contributing/COMMITS.md](docs/contributing/COMMITS.md) |
| Documentation rules | [docs/contributing/DOCUMENTATION.md](docs/contributing/DOCUMENTATION.md) |

---

## API at a glance

Nineteen endpoints across five routers, plus a `GET /` health check. Full detail in
[docs/api/ENDPOINTS.md](docs/api/ENDPOINTS.md).

| Group | Endpoints |
|---|---|
| Auth | `POST /api/auth/login` |
| Instances | `POST` / `GET` `/api/instances`, `GET` `/{id}`, `PATCH` `/{id}/status`, `DELETE` `/{id}`, `GET` `/{id}/diagnosis` |
| Monitoring | `GET /api/monitor/warnings` · `/errors` · `/long-stopped` · `/report` |
| Alerts | `GET /api/alerts`, `PATCH /api/alerts/{id}/resolve` |
| Clients | `POST` / `GET` `/api/clients`, `GET` `/{id}/instances` · `/cost` · `/cost-forecast` · `/sla` |

Key behaviours, each documented in [docs/business-rules/](docs/business-rules/README.md):

- **Role scoping** — ADMIN sees everything; CLIENT_MANAGER only their assigned clients.
- **Automatic alerts** — monitoring scans record alerts and skip duplicates while an
  unresolved alert of the same type exists.
- **RUNNING instances cannot be deleted** — `409 ActiveInstanceException`.
- **Cost** — SMALL $50 / MEDIUM $120 / LARGE $250 per month; the forecast counts only
  RUNNING instances.
- **SLA** — PREMIUM 99.9% / STANDARD 99% / BASIC 95%, with a documented uptime
  approximation.
- **LLM diagnosis** — falls back to a rule-based answer with no API key, so the demo
  never breaks.

---

## Project Structure

```
app/
├── main.py                  # FastAPI app, routers, exception handlers, startup seed
├── config.py                # Settings, unit pricing, SLA thresholds
├── database.py              # SQLAlchemy engine/session
├── seed.py                  # Idempotent demo data
├── models/                  # M — SQLAlchemy ORM entities
├── schemas/                 # V — Pydantic request/response DTOs
├── controllers/             # C — API routers
├── services/                # Business logic
└── core/                    # JWT security, auth dependencies, domain exceptions
docs/                        # Documentation — see docs/README.md
tests/                       # pytest integration tests
scripts/                     # Swagger UI screenshot capture
```

---

## Contributing

Documentation is written in **English** and changes in the **same commit** as the code
it describes. Before changing code, read the document covering that area — the
source-to-document mapping is in
[docs/contributing/DOCUMENTATION.md](docs/contributing/DOCUMENTATION.md).

Commit subjects carry a type prefix — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`.
See [docs/contributing/COMMITS.md](docs/contributing/COMMITS.md).
