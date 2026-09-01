# Request Conventions

Pagination, filtering, and sorting rules shared across the API.

---

## 1. Pagination

**Every list endpoint is paginated.** All seven take the same `page`/`size` pair and
answer with the same `PageResponse` envelope:

| Endpoint | Items |
|---|---|
| `GET /api/instances` | `InstanceOut` |
| `GET /api/alerts` | `AlertOut` |
| `GET /api/clients` | `ClientOut` |
| `GET /api/clients/{id}/instances` | `InstanceOut` |
| `GET /api/monitor/warnings` | `InstanceOut` |
| `GET /api/monitor/errors` | `InstanceOut` |
| `GET /api/monitor/long-stopped` | `InstanceOut` |

| Parameter | Type | Default | Bounds |
|---|---|---|---|
| `page` | int | `1` | `≥ 1` |
| `size` | int | `10` | `1 – 100` |

Response envelope (`PageResponse`):

```json
{
  "items": [ /* InstanceOut objects */ ],
  "total": 15,
  "page": 1,
  "size": 10,
  "totalPages": 2
}
```

- `total` is the count **after** filters and role scoping, not the table row count. A
  `CLIENT_MANAGER` is never told how many rows exist outside their scope.
- `totalPages` is `ceil(total / size)`.
- Requesting a page past the end returns `200` with an empty `items` array, not `404`.
- `size` is capped at `100` by the query validator; a larger value returns `422`, as does
  `page=0` or `size=0`.

The bounds, the envelope and the counting live in one place —
[app/pagination.py](../../app/pagination.py) — so the cap cannot be `100` on one route
and something else on the next.

`GET /api/monitor/report` is the exception, and is not paginated. It is a single
aggregate object rather than a list; the one list inside it, `unresolvedAlerts`, is
capped at the **20 most recent** with the full history behind `GET /api/alerts`. Its
`unresolvedAlertCount` remains the true total and can therefore exceed the length of the
embedded array — see [ENDPOINTS.md](ENDPOINTS.md#get-apimonitorreport--aggregate-report).

**Detection is not paginated, only its response.** The three `/api/monitor/*` scan
endpoints record an alert for **every** instance meeting their condition, not merely the
page they return. Paginating the recording would mean a dashboard reading page 1 silently
stopped detecting anything past it — see
[../business-rules/ALERTING.md § 2](../business-rules/ALERTING.md#2-detection-writes-alerts).

Only `GET /api/instances` was paginated originally; the other six returned every matching
row, which made the response grow without bound on tables nothing prunes. Extending the
convention is [../performance/PERFORMANCE_BUGS.md § PERF-07](../performance/PERFORMANCE_BUGS.md#perf-07),
and it is a **breaking** change to those six response shapes.

---

## 2. Filtering

Filters combine with `AND`. Omitting a parameter disables that filter.

### `GET /api/instances`

| Parameter | Type | Matching |
|---|---|---|
| `status` | `RUNNING` \| `STOPPED` \| `ERROR` | exact |
| `clientId` | int | exact |
| `region` | string | exact, case-sensitive |
| `instanceType` | `SMALL` \| `MEDIUM` \| `LARGE` | exact |

`clientId` is applied **in addition to** role scoping, never instead of it. A
`CLIENT_MANAGER` passing another manager's `clientId` gets an empty list — the filter
narrows visibility and can never widen it.

### `GET /api/alerts`

| Parameter | Type | Matching |
|---|---|---|
| `alertType` | `CPU_HIGH` \| `ERROR_DETECTED` \| `LONG_STOPPED` | exact |
| `isResolved` | bool | exact |
| `dateFrom` | date `YYYY-MM-DD` | `detectedAt` on or after |
| `dateTo` | date `YYYY-MM-DD` | `detectedAt` on or before |

`dateFrom` / `dateTo` are inclusive dates, not timestamps.

---

## 3. Sorting

`GET /api/instances` takes a single `sort` parameter. Prefix with `-` for descending:

```
GET /api/instances?sort=cpuUsage      # ascending
GET /api/instances?sort=-cpuUsage     # descending, highest CPU first
```

Sortable fields (`SORTABLE_FIELDS` in
[app/services/instance_service.py](../../app/services/instance_service.py)):

`id`, `instanceName`, `region`, `instanceType`, `status`, `cpuUsage`, `monthlyCost`,
`clientId`, `launchedAt`, `updatedAt`

An unknown field **silently falls back to `id`** rather than returning `400`. The
whitelist is what makes that safe: the sort key is interpolated into an ORM column
lookup, so rejecting-by-default prevents both errors and attribute injection. The
trade-off is that a typo produces default ordering instead of a loud failure — check the
`sort` value if results look unordered.

Sorting is applied before pagination, so page boundaries are stable across requests.
**`id` is appended as a final tiebreaker** whenever the sort key is something else. Most
sortable fields are not unique — `status` has three distinct values across the whole
table — and rows tied on the sort key have no defined order between them, so without a
unique last key a row could appear on two pages, or on none, as a caller walks them.

`GET /api/alerts` sorts the same way for the same reason: `detectedAt` descending, then
`id` descending. A scan stamps every alert it records with the same instant, so ties are
the normal case there rather than the exception. The tiebreaker is free — SQLite already
holds `ix_alerts_detectedAt` in `(detectedAt, rowid)` order, so the plan is unchanged and
still needs no sort step
([../performance/PERFORMANCE_BUGS.md § PERF-04](../performance/PERFORMANCE_BUGS.md#perf-04)).

---

## 4. Timestamps

All datetimes are ISO-8601 in UTC (`2026-08-21T14:07:00`), produced by the shared
`utcnow()` helper in [app/models/models.py](../../app/models/models.py). There is no
timezone parameter; clients localise for display.

`updatedAt` deserves special mention — it is the system's only record of *when the
status last changed*, and both the 48-hour long-stopped rule and the SLA uptime
approximation read it. See
[../business-rules/INSTANCE_LIFECYCLE.md](../business-rules/INSTANCE_LIFECYCLE.md).

---

## 5. Related

| Document | Why |
|---|---|
| [ENDPOINTS.md](ENDPOINTS.md) | Which endpoint accepts which parameter |
| [ERRORS.md](ERRORS.md) | What an out-of-range parameter returns |
| [../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md) | How role scoping interacts with filters |
