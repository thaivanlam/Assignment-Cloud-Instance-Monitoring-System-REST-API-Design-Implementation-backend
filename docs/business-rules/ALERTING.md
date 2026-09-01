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

**A scan detects over every match; it returns one page of them.** The three endpoints are
paginated ([../api/CONVENTIONS.md § 1](../api/CONVENTIONS.md#1-pagination)), and the page
bounds the *response* only. `GET /api/monitor/warnings?size=10` against 700 high-CPU
instances still opens 700 `CPU_HIGH` alerts; it just answers with ten of the instances and
a `total` of 700.

This asymmetry is deliberate and load-bearing. Recording only what the page returns would
make detection depend on how a dashboard happened to page through the results — an
instance on page 8 would never raise an alert unless somebody scrolled that far, and the
alert, not the response, is the point of the scan. The scan therefore walks the whole
matching set in id batches of `ID_BATCH_SIZE`, recording as it goes, and keeps only the
requested window
([monitor_service.py](../../app/services/monitor_service.py), `_scan`). The batching
bounds what a scan holds in memory without bounding what it detects; it is invisible
through the API, and
[tests/test_member_c.py](../../tests/test_member_c.py) pins that by driving the same scans
at several batch sizes and asserting identical instances and identical alert counts.

---

## 3. Duplicate prevention

Before inserting, a scan checks for an existing alert with the **same `instanceId`, the
same `alertType`, and `isResolved == false`**. Where one exists, the insert is skipped.

`_record_alerts()` applies that check to the whole scan at once: one query reads back
which of the scanned instances already carry an unresolved alert of the type being
recorded, and the instances missing from that set are inserted as a batch. The rule is
per instance exactly as before — this is one statement for a scan rather than two per
instance, and it is invisible through the API
([../performance/PERFORMANCE_BUGS.md § PERF-05](../performance/PERFORMANCE_BUGS.md#perf-05)).

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
`alertType`, `isResolved`, and a `detectedAt` date range, one page at a time
([../api/CONVENTIONS.md](../api/CONVENTIONS.md)).

`alerts` is the fastest-growing table in the schema — the scans above append to it and
nothing prunes it — so the history is the one listing that had to be bounded first
([../performance/PERFORMANCE_BUGS.md § PERF-07](../performance/PERFORMANCE_BUGS.md#perf-07)).
Ordering is `detectedAt` descending with `id` descending as the tiebreaker: a scan stamps
every alert it records with the same instant, so ties are the normal case, and without a
unique last key an alert could land on two pages or on none as a caller walks them.

Alerts are deleted along with their instance
([INSTANCE_LIFECYCLE.md](INSTANCE_LIFECYCLE.md)), so history does not survive instance
deletion. That rule is load-bearing for the listing, not just tidy: an alert carries no
`clientId`, so scoping a `CLIENT_MANAGER` means joining `instances` — and an `ADMIN`, who
has no scope to apply, is served without that join
([../performance/PERFORMANCE_BUGS.md § PERF-09](../performance/PERFORMANCE_BUGS.md#perf-09)).
An alert that outlived its instance would therefore be hidden from one role and listed to
the other. The cascade is what stops such a row existing, and
[../../tests/test_alerts.py](../../tests/test_alerts.py) pins it.

---

## 6. The report

`GET /api/monitor/report` aggregates over the caller's visible instances:

| Field | Rule |
|---|---|
| `instanceCountByStatus` | Zero-filled for all three statuses, so a client consuming it never has to handle a missing key |
| `warningCount` | Same condition as `CPU_HIGH` detection — `RUNNING` and `cpuUsage ≥ 80` |
| `totalMonthlyCost` | Sum over **all** visible instances, any status — see [COST.md](COST.md) |
| `unresolvedAlertCount` | Every unresolved alert in scope, counted in SQL |
| `unresolvedAlerts` | The **20 most recent** of them, newest `detectedAt` first |

The count and the array no longer answer the same question. `unresolvedAlertCount` is the
true total and can exceed the length of `unresolvedAlerts`, which is a preview capped at
`REPORT_ALERT_LIMIT`. The report is a dashboard summary; the full history is
`GET /api/alerts`, which paginates. Previously the report built the whole unresolved list
in order to take its length, so a system with thousands of open alerts serialised every
one of them into a response whose only unbounded field nobody read to the end
([../performance/PERFORMANCE_BUGS.md § PERF-07](../performance/PERFORMANCE_BUGS.md#perf-07)).

---

## 7. Verification

[tests/test_member_c.py](../../tests/test_member_c.py) covers warning/error/long-stopped
detection, alert auto-recording, duplicate prevention across repeated scans, and the
report contents. It also pins the two rules this page states about pagination: that a
scan returning one instance per page still records an alert for all four matches, and
that the report's `unresolvedAlertCount` keeps counting past the 20 it embeds.

---

## 8. Related

| Document | Why |
|---|---|
| [INSTANCE_LIFECYCLE.md](INSTANCE_LIFECYCLE.md) | Why `updatedAt` is trustworthy |
| [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) | Why a scan that records nothing does not commit, why it dedups in one query, and why it pages its response but not its detection |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | Monitoring and alert endpoint shapes |
| [../team/MEMBER_C.md](../team/MEMBER_C.md) | Assignment scope for monitoring |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | Demonstrating dedup by scanning twice |
