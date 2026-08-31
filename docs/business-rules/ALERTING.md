# Alerting Rules

Detection thresholds, automatic recording, duplicate prevention, and resolution.
Implementation: [app/services/monitor_service.py](../../app/services/monitor_service.py)
and [app/services/alert_service.py](../../app/services/alert_service.py).

---

## 1. Alert types and detection conditions

| `alertType` | Condition | Endpoint that detects it |
|---|---|---|
| `CPU_HIGH` | `status == RUNNING` **and** `cpuUsage ≥ CPU_WARNING_THRESHOLD` (default `80.0`) | `GET /api/monitor/warnings` |
| `ERROR_DETECTED` | `status == ERROR` | `GET /api/monitor/errors` |
| `LONG_STOPPED` | `status == STOPPED` **and** `updatedAt ≤ now − LONG_STOPPED_HOURS` (default `48h`) | `GET /api/monitor/long-stopped` |

`CPU_HIGH` requires `RUNNING` as well as high CPU. A stopped or failed instance has its
CPU reset to `0.0` anyway ([INSTANCE_LIFECYCLE.md](INSTANCE_LIFECYCLE.md)), but the
explicit status condition means a stale reading could never produce a warning for an
instance that is not actually running.

`LONG_STOPPED` measures from `updatedAt`, which is the closest thing the schema has to a
"stopped at" timestamp. This is exactly why the idempotent-update guard exists — a
repeated no-op `PATCH` must not restart that clock.

Generated messages embed the real values, e.g.
`CPU usage 91.5% >= 80% on instance 'vinasoft-web-01' (ap-southeast-1)` and
`[CRITICAL] Instance 'hnlog-worker-01' (ap-southeast-1) is in ERROR state`.

---

## 2. Detection writes alerts

The three detection endpoints are `GET`s that **create rows**. Calling
`/api/monitor/warnings` both returns the matching instances and records a `CPU_HIGH`
alert for each one.

This is not REST-idiomatic — a `GET` should be safe — and it is a conscious concession to
the assignment's shape: there is no scheduler or background worker in this system, so the
monitoring scan has to be triggered by something, and the read is that trigger. The
duplicate guard below is what keeps it harmless.

`GET /api/monitor/report` is the exception: it is purely read-only and never writes an
alert.

**A scan commits only when it recorded something.** Because of the duplicate guard below,
a repeat poll normally inserts nothing, and such a scan now ends without a commit at all —
it behaves as the pure read it effectively is. Only a scan that opened at least one new
alert writes. This is invisible through the API (same instances, same alerts, same
ordering) and exists because an empty commit still took an exclusive lock on the whole
SQLite database file:
[../performance/PERFORMANCE_BUGS.md § PERF-01](../performance/PERFORMANCE_BUGS.md#perf-01).

Each scan is scoped to the caller's accessible clients, so a `CLIENT_MANAGER` running a
scan only ever generates alerts for their own clients' instances
([AUTHORIZATION.md](AUTHORIZATION.md)).

---

## 3. Duplicate prevention

Before inserting, `_record_alert()` checks for an existing alert with the **same
`instanceId`, the same `alertType`, and `isResolved == false`**. If one exists, the
insert is skipped.

The consequence:

- Running the same scan ten times returns the same instances every time but leaves the
  alert count unchanged after the first call.
- The returned instance list is **not** filtered by the guard — a scan always reports
  every instance currently meeting the condition, whether or not it opened a new alert.
- The uniqueness is on the *unresolved* alert, not on the pair. Once an alert is
  resolved, the slot is free again.

Without this rule, a dashboard polling the monitoring endpoints every 30 seconds would
generate thousands of identical unresolved alerts per day and make
`unresolvedAlerts` in the report useless.

---

## 4. Resolution

`PATCH /api/alerts/{id}/resolve` sets `isResolved = true` and stamps `resolvedAt`.
Re-resolving an already-resolved alert is a no-op — the original `resolvedAt` is kept,
so the record of *when* it was handled cannot be overwritten by a repeated call.

Resolving re-arms detection: the next scan finds no unresolved alert of that type and
opens a **new** alert if the condition still holds. That is the intended behaviour —
an operator who marks a CPU alert as handled, without the CPU actually coming down,
should be told again rather than silently ignored.

Resolution is manual only. Nothing in the system auto-resolves an alert when the
underlying condition clears; an instance that recovers from `ERROR` to `RUNNING` keeps
its unresolved `ERROR_DETECTED` alert until someone resolves it. That is a known
limitation rather than an oversight — auto-resolution would erase the record that the
incident happened.

---

## 5. Alert history

`GET /api/alerts` returns alerts for the caller's accessible clients, filterable by
`alertType`, `isResolved`, and a `detectedAt` date range
([../api/CONVENTIONS.md](../api/CONVENTIONS.md)).

Alerts are deleted along with their instance
([INSTANCE_LIFECYCLE.md](INSTANCE_LIFECYCLE.md)), so history does not survive instance
deletion.

---

## 6. The report

`GET /api/monitor/report` aggregates over the caller's visible instances:

| Field | Rule |
|---|---|
| `instanceCountByStatus` | Zero-filled for all three statuses, so a client consuming it never has to handle a missing key |
| `warningCount` | Same condition as `CPU_HIGH` detection — `RUNNING` and `cpuUsage ≥ 80` |
| `totalMonthlyCost` | Sum over **all** visible instances, any status — see [COST.md](COST.md) |
| `unresolvedAlertCount` / `unresolvedAlerts` | Unresolved alerts only, newest `detectedAt` first |

---

## 7. Verification

[tests/test_member_c.py](../../tests/test_member_c.py) covers warning/error/long-stopped
detection, alert auto-recording, duplicate prevention across repeated scans, and the
report contents.

---

## 8. Related

| Document | Why |
|---|---|
| [INSTANCE_LIFECYCLE.md](INSTANCE_LIFECYCLE.md) | Why `updatedAt` is trustworthy |
| [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) | Why a scan that records nothing does not commit |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | Monitoring and alert endpoint shapes |
| [../team/MEMBER_C.md](../team/MEMBER_C.md) | Assignment scope for monitoring |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | Demonstrating dedup by scanning twice |
