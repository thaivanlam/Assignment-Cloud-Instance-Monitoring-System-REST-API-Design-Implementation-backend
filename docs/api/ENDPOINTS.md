# Endpoint Reference

Per-endpoint request and response detail. Conventions shared across endpoints —
pagination, filtering, sorting, error bodies — are in [CONVENTIONS.md](CONVENTIONS.md)
and [ERRORS.md](ERRORS.md).

All examples assume `TOKEN` holds a valid `accessToken`
([AUTHENTICATION.md](AUTHENTICATION.md)).

**Contents**

- [Health](#health)
- [Auth](#auth)
- [Instances](#instances)
- [Monitoring](#monitoring)
- [Alerts](#alerts)
- [Clients](#clients)

---

## Health

### `GET /` — Health check

No authentication.

```json
{ "status": "ok", "service": "TechValley Cloud Instance Monitoring System", "docs": "/docs" }
```

---

## Auth

### `POST /api/auth/login` — Issue a JWT

**Request** — `LoginRequest`

| Field | Type | Rules |
|---|---|---|
| `email` | string | valid email format |
| `password` | string | required |

**Response** `200` — `TokenResponse`

| Field | Type | Notes |
|---|---|---|
| `accessToken` | string | HS256 JWT, 120-minute lifetime |
| `tokenType` | string | always `"bearer"` |
| `role` | `Role` | `ADMIN` or `CLIENT_MANAGER` |
| `name` | string | display name of the member |

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@techvalley.vn","password":"admin123!"}'
```

**Errors** — `401` invalid credentials · `422` malformed email

---

## Instances

### `POST /api/instances` — Register an instance

Requires access to the target client: ADMIN always, CLIENT_MANAGER only for their own
clients.

**Request** — `InstanceCreate`

| Field | Type | Default | Rules |
|---|---|---|---|
| `instanceName` | string | — | 1–100 chars |
| `region` | string | — | 1–50 chars |
| `instanceType` | `InstanceType` | — | `SMALL` \| `MEDIUM` \| `LARGE` |
| `status` | `InstanceStatus` | `RUNNING` | optional |
| `cpuUsage` | float | `0.0` | `0.0 – 100.0` |
| `clientId` | int | — | must exist |

`monthlyCost` is **not** accepted in the request. It is derived from `instanceType` via
the unit-price table and `launchedAt` is set to the server's current UTC time. See
[../business-rules/COST.md](../business-rules/COST.md).

**Response** `201` — `InstanceOut`

```json
{
  "id": 16,
  "instanceName": "vinasoft-cache-01",
  "region": "ap-southeast-1",
  "instanceType": "MEDIUM",
  "status": "RUNNING",
  "cpuUsage": 12.0,
  "monthlyCost": 120.0,
  "clientId": 1,
  "launchedAt": "2026-08-21T09:15:00",
  "updatedAt": "2026-08-21T09:15:00"
}
```

**Errors** — `401` · `403` other manager's client · `404` unknown `clientId` · `422`

---

### `GET /api/instances` — List instances

**Query parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `page` | int | `1` | `≥ 1` |
| `size` | int | `10` | `1 – 100` |
| `status` | `InstanceStatus` | — | filter |
| `clientId` | int | — | filter, intersected with role scoping |
| `region` | string | — | exact match |
| `instanceType` | `InstanceType` | — | filter |
| `sort` | string | `id` | `-` prefix for descending; unknown field falls back to `id` |

**Response** `200` — `PageResponse[InstanceOut]`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/instances?status=RUNNING&sort=-cpuUsage&page=1&size=5"
```

```json
{ "items": [ /* InstanceOut */ ], "total": 10, "page": 1, "size": 5, "totalPages": 2 }
```

---

### `GET /api/instances/{id}` — Get one instance

**Response** `200` — `InstanceOut`
**Errors** — `401` · `403` · `404`

---

### `PATCH /api/instances/{id}/status` — Update status

**Request** — `InstanceStatusUpdate`

| Field | Type | Rules |
|---|---|---|
| `status` | `InstanceStatus` | required |
| `cpuUsage` | float \| null | optional, `0.0 – 100.0` |

Behaviour, in full detail at
[../business-rules/INSTANCE_LIFECYCLE.md](../business-rules/INSTANCE_LIFECYCLE.md):

- Moving to `STOPPED` or `ERROR` **without** a `cpuUsage` value resets CPU to `0.0`.
- An update that changes neither status nor CPU is a **no-op** — `updatedAt` is left
  untouched so the 48-hour stopped clock is not restarted.
- `updatedAt` is refreshed only when something actually changed.

**Response** `200` — `InstanceOut`

```bash
curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"STOPPED"}' http://127.0.0.1:8000/api/instances/1/status
```

**Errors** — `401` · `403` · `404` · `422` CPU out of range

---

### `DELETE /api/instances/{id}` — Delete an instance

**Response** `204` — no body. The instance's alerts are removed with it (cascade).

**Errors** — `401` · `403` · `404` · **`409`** when the instance is `RUNNING`:

```json
{
  "error": "ActiveInstanceException",
  "detail": "Instance 1 is RUNNING and cannot be deleted. Stop it first."
}
```

Stop the instance first with `PATCH /api/instances/{id}/status`, then delete.

---

### `GET /api/instances/{id}/diagnosis` — LLM incident diagnosis

Sends instance metadata plus its 10 most recent alerts to Claude and returns a
three-section incident write-up. Without an `ANTHROPIC_API_KEY` — or on any provider
failure — it falls back to a deterministic rule-based diagnosis and still returns `200`.

The provider call is capped at 30 seconds with one retry, so the endpoint answers
within about a minute in the worst case; a slower provider becomes a timeout, which
is a provider failure like any other and yields `source: "rule-based"`. The handler
returns its database connection to the pool before making the call, so a diagnosis in
flight does not occupy one.

**Response** `200` — `DiagnosisResponse`

| Field | Type | Notes |
|---|---|---|
| `instanceId` | int | |
| `instanceName` | string | |
| `status` | `InstanceStatus` | status at diagnosis time |
| `diagnosis` | string | plain text: *Probable Causes* / *Recommended Actions* / *Prevention* |
| `source` | string | `"llm"` or `"rule-based"` |

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/instances/5/diagnosis
```

Full design, prompt, and fallback behaviour:
[../design/LLM_FEATURE.md](../design/LLM_FEATURE.md).

**Errors** — `401` · `403` · `404`. Never `5xx` for LLM problems.

---

## Monitoring

All four monitoring endpoints are scoped to the caller's accessible clients. The first
three **write alerts as a side effect** of the read, skipping any instance that already
has an unresolved alert of that type — see
[../business-rules/ALERTING.md](../business-rules/ALERTING.md).

The three scans take `page` and `size` ([CONVENTIONS.md](CONVENTIONS.md#1-pagination))
and answer with a `PageResponse`. **Pagination bounds the response, not the detection**:
each records an alert for every instance meeting its condition, including instances on
pages the caller never requests. `total` is therefore the number of instances currently
matching, and the alert count after a first scan matches it — not the length of `items`.

### `GET /api/monitor/warnings` — High-CPU instances

Returns `RUNNING` instances with `cpuUsage ≥ 80`, ordered by `id`, and records a
`CPU_HIGH` alert for each.

**Query parameters** — `page` (default `1`), `size` (default `10`, max `100`)

**Response** `200` — `PageResponse[InstanceOut]`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/monitor/warnings?page=1&size=20"
```

### `GET /api/monitor/errors` — Failed instances

Returns instances in `ERROR` status and records a critical `ERROR_DETECTED` alert for
each.

**Query parameters** — `page`, `size`

**Response** `200` — `PageResponse[InstanceOut]`

### `GET /api/monitor/long-stopped` — Idle instances

Returns instances that have been `STOPPED` for at least 48 hours, measured from
`updatedAt`, and records a `LONG_STOPPED` alert for each.

**Query parameters** — `page`, `size`

**Response** `200` — `PageResponse[InstanceOut]`

### `GET /api/monitor/report` — Aggregate report

Read-only; creates no alerts.

**Response** `200` — `MonitorReport`

| Field | Type | Notes |
|---|---|---|
| `generatedAt` | datetime | server time the report was built |
| `instanceCountByStatus` | `{string: int}` | always contains `RUNNING`, `STOPPED`, `ERROR` — zero-filled |
| `warningCount` | int | RUNNING instances with `cpuUsage ≥ 80` |
| `totalMonthlyCost` | float | sum of `monthlyCost` over **all** visible instances, not only RUNNING |
| `unresolvedAlertCount` | int | **every** unresolved alert in scope, counted in SQL |
| `unresolvedAlerts` | `AlertOut[]` | the **20 most recent** only, newest first |

```json
{
  "generatedAt": "2026-08-21T09:20:00",
  "instanceCountByStatus": { "RUNNING": 10, "STOPPED": 3, "ERROR": 2 },
  "warningCount": 4,
  "totalMonthlyCost": 2100.0,
  "unresolvedAlertCount": 9,
  "unresolvedAlerts": [ /* AlertOut */ ]
}
```

`unresolvedAlertCount` is a count, not a length. The embedded `unresolvedAlerts` array
is capped at the 20 most recent, so on a busy system the count is larger than the array —
the report is a dashboard summary, and the full history is `GET /api/alerts`, which
paginates. Before the cap the report loaded and serialised every unresolved alert a
caller could see purely to report that number, on the fastest-growing table in the schema
([../performance/PERFORMANCE_BUGS.md § PERF-07](../performance/PERFORMANCE_BUGS.md#perf-07)).

The report itself takes no `page` or `size`: it is one aggregate object, not a list.

`totalMonthlyCost` counting every instance is intentional: a stopped instance still
carries its committed monthly cost. The RUNNING-only calculation belongs to the
forecast endpoint. See [../business-rules/COST.md](../business-rules/COST.md).

---

## Alerts

### `GET /api/alerts` — Alert history

**Query parameters**

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `page` | int | `1` | `≥ 1` |
| `size` | int | `10` | `1 – 100` |
| `alertType` | `AlertType` | — | `CPU_HIGH` \| `ERROR_DETECTED` \| `LONG_STOPPED` |
| `isResolved` | bool | — | |
| `dateFrom` | date `YYYY-MM-DD` | — | `detectedAt` on or after, inclusive |
| `dateTo` | date `YYYY-MM-DD` | — | `detectedAt` on or before, inclusive |

**Response** `200` — `PageResponse[AlertOut]`, ordered by `detectedAt` descending (newest
first), ties broken by `id` descending

`AlertOut`:

| Field | Type |
|---|---|
| `id` | int |
| `instanceId` | int |
| `alertType` | `AlertType` |
| `message` | string |
| `isResolved` | bool |
| `detectedAt` | datetime |
| `resolvedAt` | datetime \| null |

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/alerts?alertType=CPU_HIGH&isResolved=false&size=50"
```

`alerts` is the fastest-growing table in the schema — the monitoring scans append to it
and nothing prunes it — so `total` here is a number that keeps climbing, and walking the
history takes pages.

---

### `PATCH /api/alerts/{id}/resolve` — Resolve an alert

Sets `isResolved = true` and stamps `resolvedAt`. Once resolved, the dedup guard no
longer suppresses that alert type, so the next monitoring scan may open a fresh alert if
the condition still holds.

Resolving an already-resolved alert is a no-op: it returns `200` with the original
`resolvedAt` preserved rather than overwriting the timestamp.

**Response** `200` — `AlertOut`
**Errors** — `401` · `403` alert belongs to another manager's client · `404` unknown alert id

---

## Clients

### `POST /api/clients` — Register a client

**ADMIN only.**

**Request** — `ClientCreate`

| Field | Type | Rules |
|---|---|---|
| `clientName` | string | 1–100 chars |
| `contractPlan` | `ContractPlan` | `BASIC` \| `STANDARD` \| `PREMIUM` |
| `managerId` | int | must exist **and** have role `CLIENT_MANAGER` |

**Response** `201` — `ClientOut` (`id`, `clientName`, `contractPlan`, `managerId`, `createdAt`)

**Errors** — `401` · `403` caller is not ADMIN · `404` unknown `managerId` ·
`400` `managerId` belongs to an ADMIN rather than a CLIENT_MANAGER · `422`

---

### `GET /api/clients` — List clients

Scoped by role: ADMIN sees all, CLIENT_MANAGER sees only their own. Ordered by `id`.

**Query parameters** — `page` (default `1`), `size` (default `10`, max `100`)

**Response** `200` — `PageResponse[ClientOut]`. `total` is the scoped count, so a
`CLIENT_MANAGER` is never told how many clients exist outside their scope.

---

### `GET /api/clients/{id}/instances` — Instances of a client

**Query parameters** — `page` (default `1`), `size` (default `10`, max `100`)

**Response** `200` — `PageResponse[InstanceOut]`, ordered by `id`
**Errors** — `401` · `403` · `404`

The cost and SLA endpoints below are **not** paginated even though they embed a row per
instance: their arithmetic covers every instance of the client, so the rows are loaded
regardless. The page bound here does not apply to them.

---

### `GET /api/clients/{id}/cost` — Current-month cost

**Response** `200` — `ClientCostResponse`

| Field | Type | Notes |
|---|---|---|
| `clientId` | int | |
| `clientName` | string | |
| `month` | string | `YYYY-MM`, current month |
| `instanceCount` | int | all instances, any status |
| `totalMonthlyCost` | float | sum of `monthlyCost`, rounded to 2 decimals |
| `costByInstance` | array | `instanceId`, `instanceName`, `instanceType`, `status`, `monthlyCost` |

---

### `GET /api/clients/{id}/cost-forecast` — Next-month forecast

Counts only **currently RUNNING** instances.

**Response** `200` — `CostForecastResponse`

| Field | Type | Notes |
|---|---|---|
| `clientId` | int | |
| `clientName` | string | |
| `forecastMonth` | string | `YYYY-MM`, next calendar month |
| `runningInstanceCount` | int | |
| `forecastCost` | float | Σ subtotals |
| `breakdown` | `{type: {count, unitPrice, subtotal}}` | only types with at least one RUNNING instance appear |

```json
{
  "clientId": 1,
  "clientName": "VinaSoft",
  "forecastMonth": "2026-09",
  "runningInstanceCount": 2,
  "forecastCost": 500.0,
  "breakdown": { "LARGE": { "count": 2, "unitPrice": 250.0, "subtotal": 500.0 } }
}
```

---

### `GET /api/clients/{id}/sla` — SLA uptime

**Response** `200` — `SlaResponse`

| Field | Type | Notes |
|---|---|---|
| `clientId` | int | |
| `clientName` | string | |
| `contractPlan` | `ContractPlan` | |
| `slaThreshold` | float | `99.9` PREMIUM / `99.0` STANDARD / `95.0` BASIC |
| `month` | string | `YYYY-MM`, current month |
| `uptimePercent` | float | average across instances, 3 decimals |
| `isViolation` | bool | `uptimePercent < slaThreshold` |
| `instanceDetails` | array | `instanceId`, `instanceName`, `status`, `measuredHours`, `runningHours`, `uptimePercent` |

A client with no instances reports `uptimePercent: 100.0` and `isViolation: false`.
The uptime figure is an approximation — the schema has no status-history table. Method
and its limits: [../business-rules/SLA.md](../business-rules/SLA.md).

---

## Related

| Document | Why |
|---|---|
| [CONVENTIONS.md](CONVENTIONS.md) | Pagination, filtering, sorting in detail |
| [ERRORS.md](ERRORS.md) | Every failure body |
| [../business-rules/](../business-rules/README.md) | The rules these endpoints implement |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | A runnable sequence of these calls |
| [../design/ERD.md](../design/ERD.md) | Underlying tables and columns |
