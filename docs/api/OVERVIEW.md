# API Overview

| Item | Value |
|---|---|
| Base URL (local) | `http://127.0.0.1:8000` |
| Interactive docs | `http://127.0.0.1:8000/docs` (Swagger UI) |
| OpenAPI schema | `http://127.0.0.1:8000/openapi.json` |
| API version | `1.0.0` — declared in [app/main.py](../../app/main.py) |
| Content type | `application/json` for every request and response body |
| Field naming | camelCase everywhere — request bodies, responses, and database columns |

---

## 1. Endpoint map

Every endpoint except `GET /` and `POST /api/auth/login` requires a Bearer token.
Detailed request/response shapes are in [ENDPOINTS.md](ENDPOINTS.md).

| Tag | Method | Path | Purpose |
|---|---|---|---|
| Health | `GET` | `/` | Liveness probe |
| Auth | `POST` | `/api/auth/login` | Exchange credentials for a JWT |
| Instances | `POST` | `/api/instances` | Register an instance |
| Instances | `GET` | `/api/instances` | List with pagination / filter / sort |
| Instances | `GET` | `/api/instances/{id}` | Fetch one instance |
| Instances | `PATCH` | `/api/instances/{id}/status` | Update status and optional CPU usage |
| Instances | `DELETE` | `/api/instances/{id}` | Delete — blocked while RUNNING |
| Instances | `GET` | `/api/instances/{id}/diagnosis` | LLM incident diagnosis |
| Monitoring | `GET` | `/api/monitor/warnings` | CPU ≥ 80% instances, paginated (+ auto alerts) |
| Monitoring | `GET` | `/api/monitor/errors` | ERROR instances, paginated (+ auto alerts) |
| Monitoring | `GET` | `/api/monitor/long-stopped` | STOPPED ≥ 48h instances, paginated (+ auto alerts) |
| Monitoring | `GET` | `/api/monitor/report` | Aggregate status report |
| Alerts | `GET` | `/api/alerts` | Alert history, paginated, with filters |
| Alerts | `PATCH` | `/api/alerts/{id}/resolve` | Mark an alert resolved |
| Clients | `POST` | `/api/clients` | Register a client — ADMIN only |
| Clients | `GET` | `/api/clients` | List clients visible to the caller, paginated |
| Clients | `GET` | `/api/clients/{id}/instances` | Instances of one client, paginated |
| Clients | `GET` | `/api/clients/{id}/cost` | Current-month cost total |
| Clients | `GET` | `/api/clients/{id}/cost-forecast` | Next-month forecast |
| Clients | `GET` | `/api/clients/{id}/sla` | SLA uptime and violation flag |

Routers are registered in [app/main.py](../../app/main.py) and each lives in its own
module under [app/controllers/](../../app/controllers/).

**All seven list endpoints paginate.** They share one `page`/`size` pair and one
`PageResponse` envelope, defined in [app/pagination.py](../../app/pagination.py) and
documented in [CONVENTIONS.md § 1](CONVENTIONS.md#1-pagination). `GET /api/monitor/report`
is the only `GET` returning a collection that does not, because it is an aggregate object
rather than a list; the `unresolvedAlerts` inside it is capped at the 20 most recent.

---

## 2. Enumerations

Enum values are sent and received as their **uppercase string names**.

| Enum | Values | Used by |
|---|---|---|
| `Role` | `ADMIN`, `CLIENT_MANAGER` | `members.role`, JWT `role` claim |
| `ContractPlan` | `BASIC`, `STANDARD`, `PREMIUM` | `clients.contractPlan`, SLA threshold lookup |
| `InstanceType` | `SMALL`, `MEDIUM`, `LARGE` | `instances.instanceType`, unit pricing |
| `InstanceStatus` | `RUNNING`, `STOPPED`, `ERROR` | `instances.status` |
| `AlertType` | `CPU_HIGH`, `ERROR_DETECTED`, `LONG_STOPPED` | `alerts.alertType` |

An unrecognised enum value is rejected by Pydantic with `422` before it reaches any
service. See [ERRORS.md](ERRORS.md).

---

## 3. Naming and formats

- **camelCase field names** (`clientId`, `cpuUsage`, `launchedAt`) mirror the assignment
  specification exactly, at both the API and the database layer. There is no
  snake_case ↔ camelCase translation step.
- **Timestamps** are ISO-8601 in UTC, e.g. `2026-08-21T14:07:00`. Every model uses a
  shared `utcnow()` helper so `launchedAt`, `updatedAt`, `detectedAt`, `resolvedAt`, and
  `generatedAt` are on one clock.
- **Money** is USD, serialised as a `float` rounded to 2 decimals in aggregates
  (`totalMonthlyCost`, `forecastCost`).
- **Percentages** are `0.0 – 100.0` floats, not `0.0 – 1.0` ratios. `cpuUsage` is
  validated in that range; `uptimePercent` is rounded to 3 decimals.

---

## 4. Health check

```http
GET /
```

```json
{ "status": "ok", "service": "TechValley Cloud Instance Monitoring System", "docs": "/docs" }
```

No authentication. Useful for confirming the app started and the seed ran.

---

## 5. Next

| Document | Contents |
|---|---|
| [AUTHENTICATION.md](AUTHENTICATION.md) | How to obtain and send a token |
| [CONVENTIONS.md](CONVENTIONS.md) | Pagination, filtering, sorting |
| [ERRORS.md](ERRORS.md) | Status codes and error bodies |
| [ENDPOINTS.md](ENDPOINTS.md) | Full per-endpoint reference |
| [../design/ERD.md](../design/ERD.md) | Data model behind these fields |
