# TechValley — Cloud Instance Monitoring System

Internal monitoring system replacing manual Excel tracking of cloud instances for 10 client
companies. Built for the TechValley Developer Track assignment.

**Stack:** Python · FastAPI · SQLAlchemy (SQLite) · JWT (PyJWT) · Swagger/OpenAPI · Anthropic Claude (LLM diagnosis)
**Architecture:** MVC — `models/` (data), `schemas/` (DTO/view), `controllers/` (routing), `services/` (business logic)

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
- The database (`monitoring.db`) is created and **seeded automatically** on first run
  (2 managers + 1 admin, 10 clients, 15 instances, cost snapshots).

### Demo accounts

| Role | Email | Password | Access |
|---|---|---|---|
| ADMIN | `admin@techvalley.vn` | `admin123!` | All clients & instances |
| CLIENT_MANAGER | `lam@techvalley.vn` | `manager123!` | Clients 1–5 only |
| CLIENT_MANAGER | `minh@techvalley.vn` | `manager123!` | Clients 6–10 only |

**How to authenticate in Swagger:** call `POST /api/auth/login`, copy the `accessToken`,
click **Authorize** (top right), and paste the token.

---

## Project Structure (MVC)

```
app/
├── main.py                  # FastAPI app, routers, exception handlers, startup seed
├── config.py                # Settings, unit pricing, SLA thresholds
├── database.py              # SQLAlchemy engine/session
├── seed.py                  # Idempotent demo data
├── models/                  # M — SQLAlchemy ORM entities (ERD implementation)
├── schemas/                 # V — Pydantic request/response DTOs
├── controllers/             # C — API routers (auth, instances, monitor, alerts, clients)
├── services/                # Business logic (instance, monitor, alert, client/cost/SLA, LLM)
└── core/                    # JWT security, auth dependencies, domain exceptions
docs/ERD.md                  # Step 1 — ERD (mermaid) + design notes
```

---

## API Summary

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/login` | Login → JWT token |
| POST | `/api/instances` | Register instance (cost auto-set from type) |
| GET | `/api/instances` | List — pagination (`page`,`size`), filters (`status`,`clientId`,`region`,`instanceType`), sort (`sort=-cpuUsage`) |
| GET | `/api/instances/{id}` | Get single instance |
| PATCH | `/api/instances/{id}/status` | Update status (+ optional cpuUsage) |
| DELETE | `/api/instances/{id}` | Delete — **RUNNING blocked → 409 ActiveInstanceException** |
| GET | `/api/instances/{id}/diagnosis` | **[LLM]** Cause & action for ERROR instance |
| GET | `/api/monitor/warnings` | CPU ≥ 80% list + auto-record `CPU_HIGH` alerts |
| GET | `/api/monitor/errors` | ERROR list + auto-record critical `ERROR_DETECTED` alerts |
| GET | `/api/monitor/long-stopped` | STOPPED ≥ 48h list (+ `LONG_STOPPED` alerts) |
| GET | `/api/monitor/report` | Count by status / warning count / total cost / unresolved alerts |
| GET | `/api/alerts` | History — filters: `alertType`, `isResolved`, `dateFrom`, `dateTo` |
| PATCH | `/api/alerts/{id}/resolve` | Mark alert resolved |
| POST | `/api/clients` | Register client (ADMIN only) |
| GET | `/api/clients` | List clients (scoped by role) |
| GET | `/api/clients/{id}/instances` | Instances by client |
| GET | `/api/clients/{id}/cost` | Current-month cost total |
| GET | `/api/clients/{id}/cost-forecast` | Next-month forecast |
| GET | `/api/clients/{id}/sla` | SLA uptime + violation flag |

---

## Core Business Logic

### 1. JWT Authentication & Authorization
- `POST /api/auth/login` issues an HS256 JWT (`sub`, `email`, `role`, `exp`).
- **ADMIN** — full access to all clients/instances; only role allowed to register clients.
- **CLIENT_MANAGER** — every list/detail endpoint is filtered to clients where
  `clients.managerId == member.id`; direct access to another manager's resource → **403**.
- Passwords stored as salted PBKDF2-SHA256 hashes.

### 2. Automatic Alert Recording
- `GET /api/monitor/warnings` — for each RUNNING instance with `cpuUsage ≥ 80`, records a
  `CPU_HIGH` alert, **skipped if an unresolved alert of that type already exists** for the instance.
- `GET /api/monitor/errors` — records a critical `ERROR_DETECTED` alert for each ERROR instance
  (same dedup rule).
- `GET /api/monitor/long-stopped` — also records `LONG_STOPPED` alerts for instances stopped 48h+.

### 3. Cost Forecast
- Unit pricing: **SMALL $50 / MEDIUM $120 / LARGE $250 per month** (configurable in `config.py`).
- Forecast = Σ (unit price × count of currently **RUNNING** instances), broken down by type.

### 4. SLA Uptime
- Ratio of RUNNING time vs total hours in the current month, compared against the plan
  threshold: **PREMIUM 99.9% / STANDARD 99% / BASIC 95%**; below threshold → `isViolation: true`.
- Since the schema has no status-history table, uptime is approximated per instance:
  measured window = `max(month start, launchedAt) → now`; a RUNNING instance counts as up for
  the whole window, a STOPPED/ERROR instance counts as up until its last status change
  (`updatedAt`). Client uptime = average across instances. The approximation is documented in
  `docs/ERD.md`.

### 5. Instance Deletion Rules
- `DELETE /api/instances/{id}` on a **RUNNING** instance raises `ActiveInstanceException`
  → HTTP **409** with a structured error body. STOPPED / ERROR instances delete normally
  (their alerts are removed with them).

### Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

The focused Member C design notes and Swagger demo flow are in [`docs/MEMBER_C.md`](docs/MEMBER_C.md).

### LLM Diagnosis (`GET /api/instances/{id}/diagnosis`)
- Sends instance metadata + recent alert history to **Claude (`claude-opus-4-8`)** via the
  official Anthropic SDK and returns a structured diagnosis (Probable Causes / Recommended
  Actions / Prevention).
- Set `ANTHROPIC_API_KEY` in `.env` to enable. Without a key the endpoint **falls back to a
  rule-based diagnosis** (response field `source` says `"llm"` or `"rule-based"`), so the demo
  never breaks.

---

## Example Flow (curl)

```bash
# Login as admin
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@techvalley.vn","password":"admin123!"}' | python -c "import sys,json;print(json.load(sys.stdin)['accessToken'])")

# High-CPU warnings (auto-records alerts)
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/monitor/warnings

# Full report
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/monitor/report

# Try deleting a RUNNING instance -> 409 ActiveInstanceException
curl -X DELETE -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/instances/1

# SLA for client 1
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/clients/1/sla

# LLM diagnosis for the ERROR instance (id 5 in seed data)
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/instances/5/diagnosis
```
