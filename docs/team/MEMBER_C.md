# Member C - Instance Status and Monitoring

This document covers the TechValley assignment scope owned by Member C.

## Responsibility

| Method | Endpoint | Behavior |
|---|---|---|
| `PATCH` | `/api/instances/{id}/status` | Update status and optional CPU usage |
| `GET` | `/api/monitor/warnings` | Return RUNNING instances with CPU usage at or above 80% (one page at a time) and create `CPU_HIGH` alerts for all of them |
| `GET` | `/api/monitor/errors` | Return ERROR instances (one page at a time) and create critical `ERROR_DETECTED` alerts for all of them |
| `GET` | `/api/monitor/long-stopped` | Return instances that have been STOPPED for at least 48 hours (one page at a time) and create `LONG_STOPPED` alerts for all of them |
| `GET` | `/api/monitor/report` | Return status counts, warning count, total monthly cost, and unresolved alerts |

All endpoints require a JWT. ADMIN can see all clients. CLIENT_MANAGER results are restricted to clients assigned to the authenticated manager.

## Business Rules

### Status update

- `cpuUsage` is optional and is validated in the range 0-100.
- Moving to STOPPED or ERROR without a CPU value resets CPU usage to `0.0`.
- Repeating an identical status update is idempotent and does not reset `updatedAt`. This preserves the STOPPED duration used by the 48-hour rule.
- A manager cannot update an instance belonging to another manager's client.

### Alert creation and duplicate prevention

Each monitoring scan checks for an unresolved alert with the same `instanceId` and `alertType` before inserting. Repeated scans therefore return the same matching instances without creating duplicate unresolved alerts. After an alert is resolved, a later scan may create a new alert if the condition still exists.

A scan records an alert for **every** instance meeting its condition, not only those on the page it returns. The three endpoints are paginated, but the pagination bounds the response and never the detection — an instance on page eight raises its alert whether or not anyone asks for page eight. See [../business-rules/ALERTING.md § 2](../business-rules/ALERTING.md#2-detection-writes-alerts).

### Full report

- `instanceCountByStatus`: includes RUNNING, STOPPED, and ERROR keys even when a count is zero.
- `warningCount`: number of RUNNING instances whose CPU usage is at least 80%.
- `totalMonthlyCost`: sum of `monthlyCost` for all visible instances. The RUNNING-only restriction belongs to the next-month forecast API, not the current report.
- `unresolvedAlertCount`: every unresolved alert within the caller's client access, counted in the database.
- `unresolvedAlerts`: the 20 most recent of them, newest first. It is a preview, so on a busy system it is shorter than `unresolvedAlertCount`; the complete history is the paginated `GET /api/alerts`.

## Demo Flow

1. Start the API and log in as ADMIN with `admin@techvalley.vn` / `admin123!`.
2. Call `/api/monitor/warnings` twice. The response is the same and the unresolved CPU alert count does not increase on the second call.
3. Call `/api/monitor/errors` and `/api/monitor/long-stopped` twice to demonstrate the same duplicate prevention.
4. Call `/api/monitor/report` to show status totals, costs, and the generated unresolved alerts.
5. Resolve one CPU alert using `/api/alerts/{id}/resolve`, call `/api/monitor/warnings` again, and show that a fresh alert is created because the previous one is resolved.
6. Log in as `lam@techvalley.vn` and show that monitoring results contain only clients 1-5. Attempt to update instance 10 to demonstrate the `403` access rule.

## Verification

```bash
pip install -r requirements-dev.txt
pytest -q
```

The Member C integration tests ([tests/test_member_c.py](../../tests/test_member_c.py)) cover authentication, role scoping, status changes, CPU normalization, warning/error/long-stopped detection, alert auto-recording, duplicate prevention, and the full report.

## Related

| Document | Why |
|---|---|
| [../business-rules/INSTANCE_LIFECYCLE.md](../business-rules/INSTANCE_LIFECYCLE.md) | Status transitions, CPU reset, idempotent updates |
| [../business-rules/ALERTING.md](../business-rules/ALERTING.md) | Detection thresholds and duplicate prevention |
| [../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md) | Role scoping applied to monitoring results |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | Request/response shapes for these endpoints |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | Parts 3–4 are this demo flow, with expected numbers |
| [../demo/SEED_DATA.md](../demo/SEED_DATA.md) | Which seeded instances trigger which alert |
