# Demo Walkthrough

An ordered script that exercises every business rule against the seeded database.
Run it in Swagger UI (`http://127.0.0.1:8000/docs`) or with the curl commands below.

Expected numbers assume a **freshly seeded** database — see
[SEED_DATA.md](SEED_DATA.md). Captured responses for each step are linked from
[../screenshots/README.md](../screenshots/README.md).

---

## Setup

```bash
uvicorn app.main:app --reload
```

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@techvalley.vn","password":"admin123!"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['accessToken'])")
```

---

## Part 1 — Auth

### 1. Health check

```bash
curl http://127.0.0.1:8000/
```

`200` — confirms the app started and the seed ran.

### 2. Login as ADMIN

`POST /api/auth/login` with `admin@techvalley.vn` / `admin123!` → `accessToken`, plus
`role: "ADMIN"` and `name`.

### 3. Wrong password

Same call with a bad password → `401 {"detail": "Invalid email or password"}`. The
message is identical for a wrong email, so accounts cannot be enumerated.

### 4. No token

```bash
curl http://127.0.0.1:8000/api/instances
```

`401 {"detail": "Not authenticated. Provide a Bearer token."}`.

---

## Part 2 — Clients

### 5. List clients as ADMIN

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/clients
```

All **10** clients, inside a `PageResponse`: `items` holds them, `total` is `10`,
`totalPages` is `1` at the default `size=10`. Every list endpoint answers in this
envelope — `curl ".../api/clients?size=4"` splits the same ten across three pages
([../api/CONVENTIONS.md § 1](../api/CONVENTIONS.md#1-pagination)).

### 6. Register a client

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"clientName":"New Client Co","contractPlan":"STANDARD","managerId":2}' \
  http://127.0.0.1:8000/api/clients
```

`201`. Passing `managerId: 1` (the ADMIN) instead returns `400 ValidationError` — a
client must be owned by a `CLIENT_MANAGER`.

---

## Part 3 — Instances

### 7. List, sorted

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/instances?sort=-cpuUsage&page=1&size=5"
```

`health-api-01` (96.3) first. `total: 15`, `totalPages: 3`.

### 8. List, filtered

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/instances?status=RUNNING&region=ap-southeast-1"
```

### 9. Get one instance

`GET /api/instances/1` → `vinasoft-web-01`, LARGE, RUNNING, 91.5% CPU, `monthlyCost: 250`.

### 10. Register an instance

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"instanceName":"demo-api-01","region":"ap-southeast-1","instanceType":"MEDIUM","clientId":1}' \
  http://127.0.0.1:8000/api/instances
```

`201`. Note `monthlyCost: 120.0` in the response — derived from `instanceType`, never
sent by the caller ([../business-rules/COST.md](../business-rules/COST.md)).

### 11. Update status

```bash
curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"STOPPED"}' http://127.0.0.1:8000/api/instances/2/status
```

`cpuUsage` drops to `0.0` even though it was not sent — moving to STOPPED/ERROR resets
it. Repeat the identical call and observe that `updatedAt` does **not** move: the update
is a no-op, which is what keeps the 48-hour stopped clock honest
([../business-rules/INSTANCE_LIFECYCLE.md](../business-rules/INSTANCE_LIFECYCLE.md)).

---

## Part 4 — Monitoring and alert deduplication

This is the core demonstration. **Call each scan twice.**

### 12. High-CPU warnings

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/monitor/warnings
```

**4** instances — ids 1, 4, 11, 14 — in `items`, with `total: 4`. Instance 10 at 78.9%
is correctly excluded.

Call it again: the same 4 instances come back, and the unresolved `CPU_HIGH` count does
**not** increase. The dedup guard skips insertion when an unresolved alert of the same
type already exists.

Worth demonstrating in the same breath, because it is the one thing about these endpoints
that surprises people. Reset the database, then:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/monitor/warnings?size=1"
```

One instance in `items`, `total: 4` — and **four** `CPU_HIGH` alerts recorded, which the
next step's report confirms. Pagination bounds the response; detection still covers every
match ([../business-rules/ALERTING.md § 2](../business-rules/ALERTING.md#2-detection-writes-alerts)).

### 13. Errors

`GET /api/monitor/errors` → **2** instances (5, 9), each with a critical
`ERROR_DETECTED` alert. Call twice; still 2 alerts.

### 14. Long-stopped

`GET /api/monitor/long-stopped` → **3** instances (3, 7, 13), stopped 72h, 120h, and 96h.
Call twice; still 3 alerts.

### 15. Full report

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/monitor/report
```

On a fresh database, before any status changes:

```json
{
  "instanceCountByStatus": { "RUNNING": 10, "STOPPED": 3, "ERROR": 2 },
  "warningCount": 4,
  "totalMonthlyCost": 2100.0,
  "unresolvedAlertCount": 9
}
```

9 = 4 CPU_HIGH + 2 ERROR_DETECTED + 3 LONG_STOPPED. `totalMonthlyCost` counts every
instance, not only running ones.

`unresolvedAlerts` beside that count holds the same 9 here, but it is capped at the 20
most recent: on a system with more open alerts than that, `unresolvedAlertCount` is the
larger number and the array is a preview. The report is a summary; the complete history
is step 16.

---

## Part 5 — Alerts

### 16. Alert history

`GET /api/alerts` → all 9 in `items`, newest first, with `total: 9`. Add `?size=4` to
walk them in three pages — the ordering breaks ties on `id`, so no alert is served twice
or skipped even though all nine share a `detectedAt`.

### 17. Filtered history

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/alerts?alertType=CPU_HIGH&isResolved=false"
```

### 18. Resolve, then rescan

```bash
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/alerts/1/resolve
```

`isResolved: true`, `resolvedAt` stamped. Now call `/api/monitor/warnings` again — a
**new** `CPU_HIGH` alert is created for that instance, because the dedup guard only
suppresses while an unresolved alert exists. The condition has not gone away, so the
operator is told again ([../business-rules/ALERTING.md](../business-rules/ALERTING.md)).

---

## Part 6 — Cost and SLA

### 19. Client instances

`GET /api/clients/1/instances` → VinaSoft's 3 instances.

### 20. Current cost

`GET /api/clients/1/cost` → `totalMonthlyCost: 620.0` across 3 instances, including the
stopped one.

### 21. Forecast

`GET /api/clients/1/cost-forecast` → `forecastCost: 500.0`, 2 RUNNING LARGE instances.
The difference from step 20 is the stopped MEDIUM instance — the forecast counts only
RUNNING ([../business-rules/COST.md](../business-rules/COST.md)).

### 22. SLA

`GET /api/clients/1/sla` → PREMIUM, `slaThreshold: 99.9`, with per-instance
`measuredHours` / `runningHours` in `instanceDetails`. Compare with a BASIC client
(`/api/clients/3/sla`, threshold 95.0) to show the plan-driven threshold
([../business-rules/SLA.md](../business-rules/SLA.md)).

---

## Part 7 — Error paths

### 23. Delete a RUNNING instance → `409`

```bash
curl -X DELETE -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/instances/1
```

```json
{
  "error": "ActiveInstanceException",
  "detail": "Instance 1 is RUNNING and cannot be deleted. Stop it first."
}
```

### 24. Unknown instance → `404`

`GET /api/instances/9999` → `{"error": "NotFound", "detail": "Instance 9999 not found"}`.

### 25. Delete a STOPPED instance → `204`

Stop instance 1 with `PATCH /api/instances/1/status`, then delete it. `204`, no body.
Its alerts are removed with it.

---

## Part 8 — Role scoping

Log in as `lam@techvalley.vn` / `manager123!` and re-authorize.

### 26. Manager sees half the data

`GET /api/clients` → clients **1–5** only.
`GET /api/monitor/report` → 9 instances, `totalMonthlyCost: 1260.0`.

Running the same calls as `minh@techvalley.vn` gives clients 6–10, 6 instances, and
`840.0`. The two managers' figures sum to the ADMIN's.

### 27. Cross-manager access → `403`

As `lam`, `GET /api/clients/10/sla` (TravelGo, owned by minh) →
`403 {"detail": "CLIENT_MANAGER can only access clients assigned to them"}`.

The API answers `403` rather than `404` — the resource is confirmed to exist. Rationale:
[../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md).

### 28. Non-ADMIN client registration → `403`

As `lam`, `POST /api/clients` → `403 {"detail": "ADMIN role required"}`.

---

## Part 9 — LLM diagnosis

### 29. Diagnose an ERROR instance

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/instances/5/diagnosis
```

Returns *Probable Causes* / *Recommended Actions* / *Prevention* and a `source` field.

With `ANTHROPIC_API_KEY` set, `source: "llm"`. Without it — or on any provider failure —
the endpoint still returns `200` with `source: "rule-based"` and logs a `WARNING`. The
status code, schema, and section structure are identical either way, which is what makes
the endpoint safe to demo offline
([../design/LLM_FEATURE.md](../design/LLM_FEATURE.md)).

A slow or unreachable provider does not stall the demo either: the call times out after
30 seconds and is retried once, so the answer arrives within about a minute at worst —
as the rule-based one, if it comes to that.

---

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

[tests/test_member_c.py](../../tests/test_member_c.py) covers authentication, role
scoping, status changes, CPU normalisation, warning/error/long-stopped detection, alert
auto-recording, duplicate prevention, and the full report.

---

## Related

| Document | Why |
|---|---|
| [SEED_DATA.md](SEED_DATA.md) | Where the expected numbers come from |
| [ACCOUNTS.md](ACCOUNTS.md) | Credentials for each part |
| [../screenshots/README.md](../screenshots/README.md) | Captured Swagger responses |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | Full reference for every call above |
