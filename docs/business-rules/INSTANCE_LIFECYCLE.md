# Instance Lifecycle Rules

Registration, status transitions, and deletion.
Implementation: [app/services/instance_service.py](../../app/services/instance_service.py).

---

## 1. Registration

`POST /api/instances` accepts the instance's identity and placement; the server derives
the rest.

| Field | Source |
|---|---|
| `instanceName`, `region`, `instanceType`, `clientId` | request body |
| `status` | request body, default `RUNNING` |
| `cpuUsage` | request body, default `0.0`, validated `0.0 – 100.0` |
| `monthlyCost` | **derived** from `instanceType` via the unit-price table |
| `launchedAt` | server UTC time at creation |
| `updatedAt` | database default, same moment |

`monthlyCost` is not accepted from the client. Pricing is a business rule, not caller
input — see [COST.md](COST.md) for why the derived value is nevertheless *stored* rather
than computed on read.

An unknown `clientId` raises `NotFoundException` → `404`, and the caller's access to
that client is checked before the row is created
([AUTHORIZATION.md](AUTHORIZATION.md)).

---

## 2. Status transitions

`PATCH /api/instances/{id}/status` takes a required `status` and an optional `cpuUsage`.

Any status may move to any other status. There is no state machine — a cloud instance
can legitimately go from `ERROR` straight to `RUNNING` after a restart, or from
`RUNNING` to `ERROR` without passing through `STOPPED`.

### 2.1 CPU reset on STOPPED / ERROR

When the target status is `STOPPED` or `ERROR` and `cpuUsage` is omitted, CPU is reset
to `0.0`.

A stopped instance is not consuming CPU, and leaving a stale figure like `91.5` behind
would keep it in the `GET /api/monitor/warnings` result set forever. Moving to
`RUNNING` without a `cpuUsage` leaves the existing value untouched — the caller has said
nothing about load, so the last known reading stands.

An explicit `cpuUsage` always wins, including `0.0` on a RUNNING instance.

### 2.2 Idempotent updates

If the request changes **neither** status nor CPU usage, the service returns the
instance unchanged and **does not touch `updatedAt`**.

This is the single most consequential rule in this file. `updatedAt` is the system's
only record of when the status last changed, and two other features read it:

- the 48-hour long-stopped detection ([ALERTING.md](ALERTING.md));
- the SLA uptime approximation ([SLA.md](SLA.md)).

Without the no-op guard, a client polling `PATCH .../status` with the same payload —
or a monitoring dashboard re-asserting known state — would restart the stopped clock on
every call, and an instance stopped for a week would never be reported as long-stopped.

`updatedAt` is refreshed only when `status` or `cpuUsage` actually changed value.

---

## 3. Deletion

`DELETE /api/instances/{id}` returns `204` with no body.

### 3.1 RUNNING instances are protected

Deleting an instance in `RUNNING` status raises `ActiveInstanceException` → **`409`**:

```json
{
  "error": "ActiveInstanceException",
  "detail": "Instance 1 is RUNNING and cannot be deleted. Stop it first."
}
```

The rule exists because deleting the monitoring record for a live instance would leave
real infrastructure running, unmonitored and still billing, with no row to find it by.
Requiring an explicit stop first forces the operator to acknowledge the instance's state.

The correct sequence is `PATCH /api/instances/{id}/status` with `{"status": "STOPPED"}`,
then `DELETE`.

`409` — conflict with the resource's current state — is the accurate code here: the
request is well-formed and the caller is authorized; only the instance's present status
makes it impossible.

### 3.2 Alerts are removed with the instance

`STOPPED` and `ERROR` instances delete normally. Their alerts are removed by cascade,
so no orphaned alert can point at a missing `instanceId`. Historical alerts for a
deleted instance are therefore *not* retained — if audit history mattered, the delete
would need to become a soft delete.

---

## 4. Verification

Covered in [tests/test_member_c.py](../../tests/test_member_c.py): status changes, CPU
normalisation on STOPPED/ERROR, and the idempotent-update guard.

Screenshots of the `409` and the successful `204`:
[../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md).

---

## 5. Related

| Document | Why |
|---|---|
| [ALERTING.md](ALERTING.md) | Consumes `status` and `updatedAt` |
| [COST.md](COST.md) | Consumes `instanceType` and `monthlyCost` |
| [SLA.md](SLA.md) | Consumes `launchedAt`, `updatedAt`, `status` |
| [../api/CONVENTIONS.md](../api/CONVENTIONS.md) | The pagination, filtering and sorting `GET /api/instances` applies to these rows — including why `id` is appended to every sort |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | Request/response shapes |
| [../api/ERRORS.md](../api/ERRORS.md) | The `409` body |
