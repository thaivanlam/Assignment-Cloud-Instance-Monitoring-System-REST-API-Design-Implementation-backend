# Request Conventions

Pagination, filtering, and sorting rules shared across the API.

---

## 1. Pagination

Only `GET /api/instances` is paginated. Every other list endpoint returns a plain JSON
array, because the seeded scale (10 clients, 15 instances) does not justify an envelope.

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

- `total` is the count **after** filters and role scoping, not the table row count.
- `totalPages` is `ceil(total / size)`.
- Requesting a page past the end returns `200` with an empty `items` array, not `404`.
- `size` is capped at `100` by the query validator; a larger value returns `422`.

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
