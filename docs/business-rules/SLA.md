# SLA Rules

Uptime calculation and violation detection for `GET /api/clients/{id}/sla`.
Implementation: `get_sla()` in
[app/services/client_service.py](../../app/services/client_service.py).

---

## 1. Thresholds by contract plan

| `contractPlan` | Required uptime | Setting |
|---|---|---|
| `PREMIUM` | `99.9%` | `SLA_PREMIUM` |
| `STANDARD` | `99.0%` | `SLA_STANDARD` |
| `BASIC` | `95.0%` | `SLA_BASIC` |

`isViolation` is `true` when `uptimePercent < slaThreshold`. The comparison is strict —
exactly meeting the threshold is not a violation.

---

## 2. Measurement window

Uptime is calculated for the **current calendar month**, per instance:

```
window_start = max(first day of current month at 00:00 UTC, instance.launchedAt)
window_end   = now
total_hours  = window_end − window_start
```

Anchoring on `launchedAt` matters: an instance created three days ago is not penalised
for the twenty days of the month before it existed. Instances whose window is zero or
negative — launched in the future, or exactly at this instant — are skipped entirely
rather than contributing a divide-by-zero.

---

## 3. The uptime approximation

**The schema has no status-history table.** There is no record of when an instance
transitioned between statuses, only `updatedAt` — the moment of its *last* change. The
calculation therefore approximates:

| Current status | Counted as up from | Counted as up until |
|---|---|---|
| `RUNNING` | `window_start` | `now` — the whole window |
| `STOPPED` or `ERROR` | `window_start` | `min(max(updatedAt, window_start), now)` — its last status change |

```
uptimePercent (instance) = min(up_hours / total_hours, 1.0) × 100
uptimePercent (client)   = arithmetic mean across the client's instances
```

Per-instance percentages are rounded to 3 decimals and clamped at `100.0`. A client
with no instances reports `100.0` and `isViolation: false` — nothing to fail.

### 3.1 What the approximation gets wrong

Stating these plainly, because the number should not be read as a measured SLA figure:

- **Only the most recent outage counts.** An instance that failed and recovered three
  times this month is currently `RUNNING`, so it is credited with 100% uptime. Real
  downtime is under-reported.
- **The current outage is assumed to have started at the last update.** An instance
  that entered `ERROR` and was then edited for an unrelated reason has its `updatedAt`
  moved forward, shortening the apparent outage. The idempotent-update guard in
  [INSTANCE_LIFECYCLE.md](INSTANCE_LIFECYCLE.md) exists partly to limit this.
- **Instances are weighted equally.** A client's uptime is a plain average, so a
  `SMALL` test box counts as much as a `LARGE` production database. Weighting by cost
  or type would be more faithful to business impact.

Fixing all three needs the same thing: an `instance_status_history` table recording
`(instanceId, fromStatus, toStatus, changedAt)`, with uptime integrated over the real
intervals. That is the recommended next step if SLA reporting becomes contractual
rather than indicative.

---

## 4. Response detail

`instanceDetails` exposes the inputs so the figure can be audited rather than trusted
blindly:

| Field | Meaning |
|---|---|
| `instanceId`, `instanceName`, `status` | Which instance, and its status at calculation time |
| `measuredHours` | The window length, 1 decimal |
| `runningHours` | Hours counted as up, 1 decimal |
| `uptimePercent` | `runningHours / measuredHours`, 3 decimals |

An operator seeing an unexpected `isViolation` can read `measuredHours` versus
`runningHours` per instance and see exactly which one pulled the average down.

---

## 5. Related

| Document | Why |
|---|---|
| [INSTANCE_LIFECYCLE.md](INSTANCE_LIFECYCLE.md) | Why `updatedAt` is the best available signal |
| [COST.md](COST.md) | The other per-client calculation |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | `SlaResponse` shape |
| [../design/ERD.md](../design/ERD.md) | Why no status-history table exists |
