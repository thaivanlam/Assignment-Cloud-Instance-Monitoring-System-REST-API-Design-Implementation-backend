# Functional Requirements Specification

| | |
|---|---|
| System | TechValley Cloud Instance Monitoring System |
| Document | Functional Requirements Specification (FRS / FRD) |
| Status | Baseline — describes the delivered system |
| Owner | TechValley Developer Track team |
| Last reviewed | 2026-09-01 |

How each function of the system behaves, in the detail needed to build it or to write a
test for it: inputs and their validation, processing rules in order, outputs, and every
failure path. The business need is [BRD.md](BRD.md); the requirement each function
realises is in [SRS.md](SRS.md).

This document is *specification*. The delivered request/response shapes are mirrored in
[../api/ENDPOINTS.md](../api/ENDPOINTS.md), and the reasoning behind the rules is in
[../business-rules/](../business-rules/README.md) — where a rule is subtle, the spec links
there rather than repeating the argument.

---

## Function index

| ID | Function | Endpoint | Roles |
|---|---|---|---|
| [F-AUTH-01](#f-auth-01--log-in) | Log in | `POST /api/auth/login` | Anonymous |
| [F-AUTH-02](#f-auth-02--authenticate-a-request) | Authenticate a request | *(every protected endpoint)* | Any member |
| [F-AUTH-03](#f-auth-03--health-check) | Health check | `GET /` | Anonymous |
| [F-INST-01](#f-inst-01--register-an-instance) | Register an instance | `POST /api/instances` | ADMIN, MANAGER |
| [F-INST-02](#f-inst-02--list-instances) | List instances | `GET /api/instances` | ADMIN, MANAGER |
| [F-INST-03](#f-inst-03--read-one-instance) | Read one instance | `GET /api/instances/{id}` | ADMIN, MANAGER |
| [F-INST-04](#f-inst-04--update-status) | Update status | `PATCH /api/instances/{id}/status` | ADMIN, MANAGER |
| [F-INST-05](#f-inst-05--delete-an-instance) | Delete an instance | `DELETE /api/instances/{id}` | ADMIN, MANAGER |
| [F-MON-01](#f-mon-01--scan-for-high-cpu-instances) | Scan: high CPU | `GET /api/monitor/warnings` | ADMIN, MANAGER |
| [F-MON-02](#f-mon-02--scan-for-failed-instances) | Scan: failed | `GET /api/monitor/errors` | ADMIN, MANAGER |
| [F-MON-03](#f-mon-03--scan-for-long-stopped-instances) | Scan: long-stopped | `GET /api/monitor/long-stopped` | ADMIN, MANAGER |
| [F-MON-04](#f-mon-04--aggregate-monitoring-report) | Aggregate report | `GET /api/monitor/report` | ADMIN, MANAGER |
| [F-ALRT-01](#f-alrt-01--list-alert-history) | Alert history | `GET /api/alerts` | ADMIN, MANAGER |
| [F-ALRT-02](#f-alrt-02--resolve-an-alert) | Resolve an alert | `PATCH /api/alerts/{id}/resolve` | ADMIN, MANAGER |
| [F-CLNT-01](#f-clnt-01--register-a-client) | Register a client | `POST /api/clients` | **ADMIN only** |
| [F-CLNT-02](#f-clnt-02--list-clients) | List clients | `GET /api/clients` | ADMIN, MANAGER |
| [F-CLNT-03](#f-clnt-03--list-a-clients-instances) | A client's instances | `GET /api/clients/{id}/instances` | ADMIN, MANAGER |
| [F-CLNT-04](#f-clnt-04--current-month-cost) | Current-month cost | `GET /api/clients/{id}/cost` | ADMIN, MANAGER |
| [F-CLNT-05](#f-clnt-05--next-month-cost-forecast) | Next-month forecast | `GET /api/clients/{id}/cost-forecast` | ADMIN, MANAGER |
| [F-CLNT-06](#f-clnt-06--sla-uptime) | SLA uptime | `GET /api/clients/{id}/sla` | ADMIN, MANAGER |
| [F-DIAG-01](#f-diag-01--diagnose-an-instance) | Diagnose an instance | `GET /api/instances/{id}/diagnosis` | ADMIN, MANAGER |
| [F-X-01](#f-x-01--pagination) | Pagination | *(all list endpoints)* | — |
| [F-X-02](#f-x-02--role-scoping) | Role scoping | *(all endpoints)* | — |
| [F-X-03](#f-x-03--error-mapping) | Error mapping | *(all endpoints)* | — |

"MANAGER" throughout means a member with role `CLIENT_MANAGER`, always restricted to
their own clients by [F-X-02](#f-x-02--role-scoping).

---

## Cross-cutting functions

These three apply to every function below. They are specified once so the per-function
sections can state only what is unique to them.

### F-X-01 — Pagination

| | |
|---|---|
| **Applies to** | The seven list endpoints: instances, alerts, clients, a client's instances, and the three monitoring scans |
| **Realises** | FR-10, BR-18 |
| **Verified by** | `list_instances_paginates`, `alert_history_is_paginated`, `client_list_is_paginated`, `monitoring_pages_partition_the_matches` |

**Inputs**

| Parameter | Type | Default | Rule |
|---|---|---|---|
| `page` | int | `1` | `≥ 1`, else `422` |
| `size` | int | `10` | `1–100`, else `422` |

**Processing**

1. Build the query with the endpoint's filters **and** the caller's scope
   ([F-X-02](#f-x-02--role-scoping)).
2. Count the filtered, scoped rows — this is `total`. The count drops any `ORDER BY`
   first: a sort cannot change how many rows exist, and leaving it on makes the database
   sort the whole set to count it.
3. Apply the endpoint's ordering, always ending in a **unique** key so ties cannot move
   rows between pages.
4. Skip `(page − 1) × size` rows, take `size`.
5. `totalPages = ceil(total / size)`.

**Output** — the `PageResponse` envelope, identical on all seven:

| Field | Type | Meaning |
|---|---|---|
| `items` | array | The requested window, possibly empty |
| `total` | int | Rows after filtering **and** scoping — never the table row count |
| `page` | int | Echoed back |
| `size` | int | Echoed back |
| `totalPages` | int | `ceil(total / size)` |

**Rules that are easy to get wrong**

- A page past the end is `200` with an empty `items`, **not** `404`.
- `total` must never leak rows outside the caller's scope — a manager with 5 clients sees
  `total: 5`, not `10`.
- For the three scans, pagination bounds the **response only**; detection still covers
  every match ([F-MON-01](#f-mon-01--scan-for-high-cpu-instances)).
- Cost and SLA are **not** paginated: their arithmetic covers every instance of the
  client, so a page would produce a wrong total.

Reference: [../api/CONVENTIONS.md § 1](../api/CONVENTIONS.md#1-pagination).

### F-X-02 — Role scoping

| | |
|---|---|
| **Applies to** | Every endpoint except `GET /` and `POST /api/auth/login` |
| **Realises** | FR-10, BR-03, BR-04 |
| **Verified by** | `list_instances_is_scoped_to_the_callers_clients`, `alert_history_is_scoped_to_the_callers_clients`, `client_sub_resources_enforce_scope_and_existence`, `a_manager_with_no_clients_sees_nothing` |

**Processing — two paths, chosen by endpoint shape**

| Path | Used by | Rule |
|---|---|---|
| **Filter at the query** | List endpoints | Resolve the caller's accessible client ids. `ADMIN` → no filter at all. `CLIENT_MANAGER` → the ids of clients they manage, pushed into a SQL `IN (…)`. A manager with **zero** clients yields `IN (-1)`, an id that can never match, so the result is empty rather than unfiltered |
| **Check after load** | Single-resource endpoints | Load the row, walk to its owning client, and compare. `ADMIN` passes immediately; a manager whose id differs from `client.managerId` gets `403` |

**Rules**

1. A query parameter may only narrow visibility. `?clientId=` is `AND`-ed with the scope,
   so a manager passing another manager's client id gets an **empty list**, not `403`.
2. For a single resource across the scope boundary the answer is `403`, not `404` — a
   deliberate trade-off recorded in
   [AUTHORIZATION § 3](../business-rules/AUTHORIZATION.md#3-403-rather-than-404).
3. Scope is checked **before** a write. Registering an instance under another manager's
   client is refused before any row is created.
4. Role is read from the member row loaded on this request, never from the token's claim.

### F-X-03 — Error mapping

| | |
|---|---|
| **Applies to** | Every endpoint |
| **Realises** | FR-10, NFR-USE-02 |
| **Verified by** | Failure cases in every suite |

| Condition | Status | Body shape |
|---|---|---|
| Schema validation failure (type, range, enum, missing field, bad date) | `422` | FastAPI's `{"detail": [ … ]}` array |
| Business-rule violation (`ValidationException`) | `400` | `{"error": "ValidationError", "detail": "…"}` |
| Missing / expired / invalid token, deleted member | `401` | `{"detail": "…"}` |
| Role or scope violation | `403` | `{"detail": "…"}` |
| Unknown instance or client (`NotFoundException`) | `404` | `{"error": "NotFound", "detail": "…"}` |
| Unknown alert id | `404` | `{"detail": "…"}` — **no `error` key**; a documented inconsistency |
| Deleting a `RUNNING` instance (`ActiveInstanceException`) | `409` | `{"error": "ActiveInstanceException", "detail": "…"}` |

**Rules**

1. Services raise domain exceptions; handlers registered on the application map them to
   status codes. No service raises an HTTP error itself.
2. No internal detail — stack trace, SQL, file path — may appear in a body.
3. A provider failure in [F-DIAG-01](#f-diag-01--diagnose-an-instance) is **never** an
   error status.

Reference: [../api/ERRORS.md](../api/ERRORS.md).

---

## Authentication

### F-AUTH-01 — Log in

| | |
|---|---|
| **Endpoint** | `POST /api/auth/login` |
| **Roles** | Anonymous |
| **Realises** | FR-01, BR-06 |
| **Verified by** | `login_returns_a_usable_token_with_role_and_name`, `login_rejects_bad_credentials_without_revealing_which_part_failed` |

**Preconditions** — none. This is one of two endpoints reachable without a token.

**Inputs**

| Field | Type | Validation |
|---|---|---|
| `email` | string | Must parse as an email address, else `422` |
| `password` | string | Required |

**Processing**

1. Look up the member by email.
2. Verify the password against the stored salted PBKDF2-SHA256 hash.
3. If either step fails, answer `401` with **one** message that does not say which failed.
4. Issue a JWT signed HS256 with claims `sub` (member id as a string), `email`, `role`,
   and `exp` = now + `ACCESS_TOKEN_EXPIRE_MINUTES` (default 120).
5. Return the token together with the member's role and display name, so a client can
   render the signed-in user without a second call.

**Output** `200`

| Field | Type | Notes |
|---|---|---|
| `accessToken` | string | The JWT |
| `tokenType` | string | Always `"bearer"` |
| `role` | enum | `ADMIN` \| `CLIENT_MANAGER` |
| `name` | string | Display name |

**Errors** — `401 Invalid email or password` (wrong email *or* wrong password) ·
`422` malformed email.

**Rule worth stating** — the identical `401` for both failures is a requirement, not an
accident: it prevents the endpoint being used to enumerate which staff accounts exist.

### F-AUTH-02 — Authenticate a request

| | |
|---|---|
| **Endpoint** | Applied to every endpoint except `GET /` and `POST /api/auth/login` |
| **Realises** | FR-01, NFR-SEC-02 |
| **Verified by** | `protected_endpoints_reject_a_missing_token`, `invalid_tokens_are_rejected`, `expired_token_is_rejected`, `token_for_a_member_that_no_longer_exists_is_rejected` |

**Inputs** — the `Authorization: Bearer <token>` header.

**Processing**

1. Absent header → `401 Not authenticated. Provide a Bearer token.`
2. Decode and verify the signature and expiry.
3. Load the member named by `sub` **from the database**.
4. Missing member → `401 Member no longer exists`.
5. Attach the loaded member to the request; every later authorization decision reads that
   row, not the token's `role` claim.

**Errors**

| Condition | Status | `detail` |
|---|---|---|
| No header | `401` | `Not authenticated. Provide a Bearer token.` |
| `exp` past | `401` | `Token has expired` |
| Bad signature or malformed | `401` | `Invalid token` |
| Member row deleted | `401` | `Member no longer exists` |

**Rule** — re-loading the member makes deletion an immediate revocation. It does **not**
provide general revocation: a valid token for an existing member cannot be stopped before
expiry ([NFR-SEC-07](SRS.md#54-security)).

### F-AUTH-03 — Health check

| | |
|---|---|
| **Endpoint** | `GET /` |
| **Roles** | Anonymous |
| **Verified by** | `health_check_is_public` |

Returns `{"status": "ok", "service": …, "docs": "/docs"}` with no authentication. Used to
confirm the process started and the seed ran.

---

## Instances

### F-INST-01 — Register an instance

| | |
|---|---|
| **Endpoint** | `POST /api/instances` |
| **Roles** | ADMIN; MANAGER for their own clients |
| **Realises** | FR-03, BR-01 |
| **Verified by** | `create_instance_derives_cost_and_applies_defaults`, `create_instance_prices_every_type`, `create_instance_is_blocked_for_another_managers_client` |

**Preconditions** — the target client exists and the caller may access it.

**Inputs**

| Field | Type | Required | Default | Validation |
|---|---|:--:|---|---|
| `instanceName` | string | ✓ | — | 1–100 characters |
| `region` | string | ✓ | — | 1–50 characters |
| `instanceType` | enum | ✓ | — | `SMALL` \| `MEDIUM` \| `LARGE` |
| `clientId` | int | ✓ | — | Must reference an existing client |
| `status` | enum | — | `RUNNING` | `RUNNING` \| `STOPPED` \| `ERROR` |
| `cpuUsage` | float | — | `0.0` | `0.0–100.0` |

`monthlyCost`, `launchedAt` and `updatedAt` are **not accepted**; supplying them has no
effect.

**Processing**

1. Load the client; unknown id → `404`.
2. Assert the caller's access to that client **before** creating anything
   ([F-X-02](#f-x-02--role-scoping)) → `403` if out of scope.
3. Derive `monthlyCost` from `instanceType` via the unit-price table
   (SMALL `50.0` / MEDIUM `120.0` / LARGE `250.0`).
4. Set `launchedAt` to the server's current UTC time; `updatedAt` takes the same moment.
5. Persist and return the created row.

**Output** `201` — the full instance record (`id`, `instanceName`, `region`,
`instanceType`, `status`, `cpuUsage`, `monthlyCost`, `clientId`, `launchedAt`,
`updatedAt`).

**Errors** — `401` · `403` another manager's client · `404` unknown `clientId` ·
`422` field validation.

**Rule** — pricing is a business rule, not caller input; deriving it server-side is what
makes [F-CLNT-04](#f-clnt-04--current-month-cost) trustworthy. Storing rather than
recomputing it means a later price change does not rewrite history
([COST § 2](../business-rules/COST.md#2-monthlycost-is-derived-but-stored)).

### F-INST-02 — List instances

| | |
|---|---|
| **Endpoint** | `GET /api/instances` |
| **Realises** | FR-03, BR-03 |
| **Verified by** | `list_instances_filters`, `list_instances_sorts`, `pages_partition_a_non_unique_sort_without_gaps_or_repeats` |

**Inputs**

| Parameter | Type | Default | Matching |
|---|---|---|---|
| `page`, `size` | int | `1`, `10` | [F-X-01](#f-x-01--pagination) |
| `status` | enum | — | Exact |
| `clientId` | int | — | Exact, intersected with scope |
| `region` | string | — | Exact, case-sensitive |
| `instanceType` | enum | — | Exact |
| `sort` | string | `id` | Field name, `-` prefix for descending |

**Processing**

1. Apply role scoping.
2. `AND` every supplied filter onto the query.
3. Resolve `sort` against the whitelist `id`, `instanceName`, `region`, `instanceType`,
   `status`, `cpuUsage`, `monthlyCost`, `clientId`, `launchedAt`, `updatedAt`. An unknown
   field **silently falls back to `id`** rather than failing.
4. Append `id` as a final tiebreaker whenever the sort key is not `id`.
5. Paginate.

**Output** `200` — `PageResponse` of instance records.

**Errors** — `401` · `422` bad `page`/`size`/enum.

**Rules**

- The sort whitelist is a security control as much as an ergonomic one: the key is used to
  look up an ORM column, so rejecting-by-default prevents attribute injection.
- The `id` tiebreaker is required for correctness. Most sortable fields are not unique —
  `status` has three values across the whole table — and without a unique last key a row
  could appear on two pages, or none, while a caller walks them.

### F-INST-03 — Read one instance

| | |
|---|---|
| **Endpoint** | `GET /api/instances/{id}` |
| **Verified by** | `get_instance_returns_the_full_record`, `get_instance_enforces_scope_and_existence` |

Load the instance; `404` if it does not exist, `403` if it belongs to another manager's
client, otherwise `200` with the full record.

### F-INST-04 — Update status

| | |
|---|---|
| **Endpoint** | `PATCH /api/instances/{id}/status` |
| **Realises** | FR-04, BR-15 |
| **Verified by** | `stopping_an_instance_resets_cpu_and_advances_updated_at`, `status_update_keeps_an_explicit_cpu_value`, `status_change_is_scoped_and_idempotent` |

**Inputs**

| Field | Type | Required | Validation |
|---|---|:--:|---|
| `status` | enum | ✓ | `RUNNING` \| `STOPPED` \| `ERROR` |
| `cpuUsage` | float \| null | — | `0.0–100.0` when present |

**Processing**

1. Load the instance and assert access (`404` / `403`).
2. Determine the target CPU value:
   - `cpuUsage` supplied → use it, including `0.0` on a running instance;
   - omitted **and** target status is `STOPPED` or `ERROR` → force `0.0`;
   - omitted **and** target status is `RUNNING` → leave the existing value untouched.
3. Compare the target `(status, cpuUsage)` with the stored pair.
   - **Unchanged** → return the instance as it is and **do not touch `updatedAt`**.
   - **Changed** → write both, and set `updatedAt` to the current UTC time.
4. Return the resulting record.

**Output** `200` — the full instance record. `monthlyCost` is never affected by a status
change.

**Errors** — `401` · `403` · `404` · `422` CPU outside `0.0–100.0`, unknown status,
missing `status`.

**Rules — both load-bearing**

- **CPU reset.** A stopped instance is not consuming CPU; leaving a stale `91.5` behind
  would keep it in the warning scan's results forever.
- **Idempotence.** `updatedAt` is the system's only record of when the status last
  changed, and both the 48-hour idle rule and the SLA calculation read it. A client
  re-asserting known state must not restart that clock
  ([INSTANCE_LIFECYCLE § 2.2](../business-rules/INSTANCE_LIFECYCLE.md#22-idempotent-updates)).

### F-INST-05 — Delete an instance

| | |
|---|---|
| **Endpoint** | `DELETE /api/instances/{id}` |
| **Realises** | FR-04, BR-14 |
| **Verified by** | `running_instance_cannot_be_deleted`, `instance_is_deleted_once_stopped`, `deleting_an_instance_removes_its_alerts` |

**Processing**

1. Load the instance and assert access (`404` / `403`).
2. If its status is `RUNNING`, refuse with `409` and the message
   `Instance {id} is RUNNING and cannot be deleted. Stop it first.`
3. Otherwise delete the row. Its alerts are removed by cascade.

**Output** `204` with no body.

**Errors** — `401` · `403` · `404` · `409` while `RUNNING`.

**Rules**

- The guard exists because deleting the record of a live instance leaves real
  infrastructure running, unmonitored and still billing, with no row to find it by. The
  operator must stop it first, which is an explicit acknowledgement of its state.
- `409` is the accurate code: the request is well-formed and authorized; only the
  resource's current state makes it impossible.
- The cascade means incident history does not outlive the instance. That is a known
  trade-off, and it is what keeps the alert listing consistent between roles
  ([ALERTING § 5](../business-rules/ALERTING.md#5-alert-history)).

---

## Monitoring

All three scans share one specification skeleton; only the detection condition, the alert
type and the message differ.

### Shared behaviour of the three scans

**Inputs** — `page`, `size` ([F-X-01](#f-x-01--pagination)).

**Processing**

1. Resolve the caller's scope.
2. Walk **every** instance matching the condition, in id order, in batches of
   `ID_BATCH_SIZE` (500).
3. For each batch, read back which of those instances already carry an **unresolved**
   alert of this type — one query for the batch, not one per instance — and insert an
   alert for the rest.
4. Commit **only if at least one alert was recorded.** A repeat scan that inserts nothing
   performs no write at all.
5. Return the requested page of the matching instances, ordered by `id`, in the standard
   envelope.

**Output** `200` — `PageResponse` of instance records.

**Errors** — `401` · `422` bad `page`/`size`.

**Rules**

| Rule | Why |
|---|---|
| A `GET` writes rows | There is no scheduler in this system; the read is the trigger. The dedup rule is what keeps it harmless |
| Detection covers all matches; pagination bounds only the response | Otherwise an instance on page 8 would raise an alert only if somebody scrolled that far — and the alert, not the response, is the point of the scan |
| The returned list is **not** filtered by the dedup rule | A scan always reports every instance currently meeting the condition, whether or not it opened a new alert |
| A scan that records nothing does not commit | An empty commit still takes an exclusive lock on the whole SQLite file, once per dashboard poll |

### F-MON-01 — Scan for high-CPU instances

| | |
|---|---|
| **Endpoint** | `GET /api/monitor/warnings` |
| **Realises** | FR-05, BR-07 |
| **Verified by** | `warnings_are_scoped_auto_recorded_and_deduplicated`, `a_scan_records_alerts_for_every_match_not_only_the_page` |

| | |
|---|---|
| **Condition** | `status == RUNNING` **and** `cpuUsage ≥ CPU_WARNING_THRESHOLD` (default `80.0`) |
| **Alert type** | `CPU_HIGH` |
| **Message** | `CPU usage 91.5% >= 80% on instance 'vinasoft-web-01' (ap-southeast-1)` |

The `RUNNING` half of the condition is deliberate. A stopped instance has its CPU reset to
`0.0` anyway, but the explicit status test means a stale reading can never raise a warning
for an instance that is not actually running.

### F-MON-02 — Scan for failed instances

| | |
|---|---|
| **Endpoint** | `GET /api/monitor/errors` |
| **Realises** | FR-05, BR-07 |
| **Verified by** | `error_and_long_stopped_monitoring_auto_record_without_duplicates` |

| | |
|---|---|
| **Condition** | `status == ERROR` |
| **Alert type** | `ERROR_DETECTED`, recorded as critical |
| **Message** | `[CRITICAL] Instance 'hnlog-worker-01' (ap-southeast-1) is in ERROR state` |

### F-MON-03 — Scan for long-stopped instances

| | |
|---|---|
| **Endpoint** | `GET /api/monitor/long-stopped` |
| **Realises** | FR-05, BR-07 |
| **Verified by** | `error_and_long_stopped_monitoring_auto_record_without_duplicates` |

| | |
|---|---|
| **Condition** | `status == STOPPED` **and** `updatedAt ≤ now − LONG_STOPPED_HOURS` (default `48`) |
| **Alert type** | `LONG_STOPPED` |

`updatedAt` is the closest thing the schema has to a "stopped at" timestamp, which is
exactly why [F-INST-04](#f-inst-04--update-status) must not move it on a no-op update.

### F-MON-04 — Aggregate monitoring report

| | |
|---|---|
| **Endpoint** | `GET /api/monitor/report` |
| **Realises** | FR-05, BR-10 |
| **Verified by** | `full_report_and_manager_scope`, `report_caps_the_embedded_alerts_but_not_the_count` |

**Processing** — read-only. This endpoint **never records an alert**. Every figure is
computed over the caller's visible instances only.

**Output** `200`

| Field | Type | Rule |
|---|---|---|
| `generatedAt` | datetime | Server time the report was built |
| `instanceCountByStatus` | `{string: int}` | Always contains `RUNNING`, `STOPPED`, `ERROR`, zero-filled, so a client never handles a missing key |
| `warningCount` | int | Same condition as [F-MON-01](#f-mon-01--scan-for-high-cpu-instances) |
| `totalMonthlyCost` | float | Sum over instances of **every** status, not only running ones |
| `unresolvedAlertCount` | int | Every unresolved alert in scope, counted in SQL |
| `unresolvedAlerts` | array | The **20 most recent** only (`REPORT_ALERT_LIMIT`), newest `detectedAt` first |

**Rules**

- `unresolvedAlertCount` is a count, not a length: on a busy estate it exceeds the length
  of `unresolvedAlerts`. The report is a dashboard summary; the full history is
  [F-ALRT-01](#f-alrt-01--list-alert-history), which paginates.
- Counting stopped instances in `totalMonthlyCost` is intentional — a stopped instance
  still carries its committed monthly cost. The running-only view is
  [F-CLNT-05](#f-clnt-05--next-month-cost-forecast).
- The report takes no `page`/`size`: it is one aggregate object, not a list.

---

## Alerts

### F-ALRT-01 — List alert history

| | |
|---|---|
| **Endpoint** | `GET /api/alerts` |
| **Realises** | FR-06, BR-08 |
| **Verified by** | `alert_history_returns_every_detection_newest_first`, `alert_history_filters_by_detection_date`, `alert_pages_partition_the_history_without_gaps_or_repeats` |

**Inputs**

| Parameter | Type | Matching |
|---|---|---|
| `page`, `size` | int | [F-X-01](#f-x-01--pagination) |
| `alertType` | enum | Exact — `CPU_HIGH` \| `ERROR_DETECTED` \| `LONG_STOPPED` |
| `isResolved` | bool | Exact |
| `dateFrom` | date `YYYY-MM-DD` | `detectedAt` on or after, inclusive of the whole day |
| `dateTo` | date `YYYY-MM-DD` | `detectedAt` on or before, inclusive of the whole day |

**Processing**

1. Scope the query. An alert carries no `clientId`, so scoping a manager means joining
   `instances`; an `ADMIN`, having no scope to apply, is served **without** that join.
2. `AND` the supplied filters.
3. Order by `detectedAt` descending, then `id` descending.
4. Paginate.

**Output** `200` — `PageResponse` of alert records (`id`, `instanceId`, `alertType`,
`message`, `isResolved`, `detectedAt`, `resolvedAt`).

**Errors** — `401` · `422` bad enum, boolean or date format.

**Rule** — the `id` tiebreaker is not cosmetic: one scan stamps every alert it records
with the same instant, so ties are the *normal* case here. Without a unique last key an
alert could land on two pages or none.

### F-ALRT-02 — Resolve an alert

| | |
|---|---|
| **Endpoint** | `PATCH /api/alerts/{id}/resolve` |
| **Realises** | FR-06, BR-08 |
| **Verified by** | `resolving_an_alert_stamps_it_once`, `resolving_removes_the_alert_from_the_report`, `resolving_another_managers_alert_is_forbidden` |

**Processing**

1. Load the alert; unknown id → `404` with a `{detail}`-only body.
2. Walk `alert → instance → client` and assert access → `403` across the scope boundary.
3. If already resolved, return it **unchanged** — the original `resolvedAt` is preserved.
4. Otherwise set `isResolved = true` and stamp `resolvedAt` with the current UTC time.

**Output** `200` — the alert record.

**Errors** — `401` · `403` · `404`.

**Rules**

- Resolution is manual. Nothing auto-resolves when a condition clears: an instance that
  recovers from `ERROR` keeps its open alert until a person closes it, because
  auto-closing would erase the evidence that the incident happened.
- Resolving **re-arms** detection. The next scan finds no unresolved alert of that type
  and opens a fresh one if the condition still holds — an operator who marks a CPU alert
  handled without the CPU coming down should be told again.
- Re-resolving must not move `resolvedAt`; the record of *when* it was handled is not
  overwritable by a repeated call.

---

## Clients, cost and SLA

### F-CLNT-01 — Register a client

| | |
|---|---|
| **Endpoint** | `POST /api/clients` |
| **Roles** | **ADMIN only** |
| **Realises** | FR-02, BR-02, BR-05 |
| **Verified by** | `admin_registers_a_client`, `client_registration_is_admin_only`, `client_registration_rejects_a_manager_id_that_is_not_a_manager` |

**Inputs**

| Field | Type | Validation |
|---|---|---|
| `clientName` | string | 1–100 characters |
| `contractPlan` | enum | `BASIC` \| `STANDARD` \| `PREMIUM` |
| `managerId` | int | Must exist **and** have role `CLIENT_MANAGER` |

**Processing**

1. Refuse any non-ADMIN caller with `403 ADMIN role required`.
2. Load the member named by `managerId`; missing → `404`.
3. If that member's role is not `CLIENT_MANAGER` → `400 ValidationError`. The whole
   scoping model assumes each client has exactly one manager owner, so a client pointed
   at an administrator would be unreachable by the manager path.
4. Create the client with `createdAt` set to the current UTC time.

**Output** `201` — `id`, `clientName`, `contractPlan`, `managerId`, `createdAt`.

**Errors** — `401` · `403` non-ADMIN · `404` unknown `managerId` · `400` manager is not a
`CLIENT_MANAGER` · `422` field validation.

**Rule** — the `400` versus `422` split is meaningful: a non-integer `managerId` is a
schema failure (`422`); an integer naming a real member with the wrong role is a
business-rule failure (`400`).

### F-CLNT-02 — List clients

| | |
|---|---|
| **Endpoint** | `GET /api/clients` |
| **Verified by** | `client_list_is_scoped_by_role`, `client_list_pagination_counts_only_the_callers_clients` |

Scoped by role — ADMIN sees all, a manager sees only their own — ordered by `id`,
paginated. `total` is the scoped count, so a manager is never told how many clients exist
outside their scope.

### F-CLNT-03 — List a client's instances

| | |
|---|---|
| **Endpoint** | `GET /api/clients/{id}/instances` |
| **Verified by** | `client_instances_are_listed_for_the_owning_manager`, `client_instances_are_paginated` |

Load the client (`404` / `403`), then return its instances ordered by `id`, paginated.

### F-CLNT-04 — Current-month cost

| | |
|---|---|
| **Endpoint** | `GET /api/clients/{id}/cost` |
| **Realises** | FR-07, BR-11 |
| **Verified by** | `current_cost_sums_every_instance_regardless_of_status`, `current_cost_follows_a_newly_registered_instance` |

**Processing**

1. Load the client (`404` / `403`).
2. Read **all** of its instances, of every status.
3. Sum `monthlyCost`, rounded to 2 decimals.
4. Report the current month as `YYYY-MM`.

**Output** `200`

| Field | Type | Notes |
|---|---|---|
| `clientId`, `clientName` | int, string | |
| `month` | string | Current month, `YYYY-MM` |
| `instanceCount` | int | All instances, any status |
| `totalMonthlyCost` | float | Rounded to 2 decimals |
| `costByInstance` | array | `instanceId`, `instanceName`, `instanceType`, `status`, `monthlyCost` — one row per instance |

**Rules**

- Stopped and failed instances are **included**: a provisioned instance costs money for
  the month whether or not it runs. `costByInstance` carries each status so the operator
  can decide what to decommission.
- Not paginated. The total must cover every instance, so the rows are loaded regardless
  and there is nothing to save by bounding the array.

### F-CLNT-05 — Next-month cost forecast

| | |
|---|---|
| **Endpoint** | `GET /api/clients/{id}/cost-forecast` |
| **Realises** | FR-07, BR-12 |
| **Verified by** | `forecast_counts_only_running_instances`, `forecast_reacts_to_a_status_change`, `forecast_of_a_client_without_running_instances_is_zero` |

**Processing**

1. Load the client (`404` / `403`).
2. Select only instances currently in `RUNNING` status.
3. Group them by `instanceType`; for each type report `count`, `unitPrice` and
   `subtotal = count × unitPrice`.
4. `forecastCost` is the sum of the subtotals.
5. `forecastMonth` is the next calendar month, `YYYY-MM`, rolling the year in December.

**Output** `200` — `clientId`, `clientName`, `forecastMonth`, `runningInstanceCount`,
`forecastCost`, `breakdown`.

**Rules**

- Types with no running instance are **absent** from `breakdown`, not present with zero.
- A client with nothing running returns `forecastCost: 0.0` and an empty `breakdown` —
  not an error.
- Straight-line projection only: no growth, seasonality or planned change is modelled.

### F-CLNT-06 — SLA uptime

| | |
|---|---|
| **Endpoint** | `GET /api/clients/{id}/sla` |
| **Realises** | FR-08, BR-13 |
| **Verified by** | `sla_reports_full_uptime_when_every_instance_is_running`, `sla_flags_a_violation_for_a_long_stopped_instance`, `sla_of_a_client_without_instances_is_not_a_violation` |

**Processing**

1. Load the client (`404` / `403`) and look up its threshold from the contract plan:
   PREMIUM `99.9`, STANDARD `99.0`, BASIC `95.0`.
2. For each instance, build the measurement window:
   `window_start = max(first day of the current month at 00:00 UTC, launchedAt)`,
   `window_end = now`. Skip any instance whose window is zero or negative.
3. Count "up" hours:
   - `RUNNING` → the whole window;
   - `STOPPED` or `ERROR` → from `window_start` to
     `min(max(updatedAt, window_start), now)` — its last status change.
4. Per instance: `uptimePercent = min(up / total, 1.0) × 100`, 3 decimals.
5. Client figure: the arithmetic mean across its instances. No instances → `100.0`.
6. `isViolation = uptimePercent < slaThreshold` — a strict comparison, so exactly meeting
   the threshold is not a violation.

**Output** `200` — `clientId`, `clientName`, `contractPlan`, `slaThreshold`, `month`,
`uptimePercent`, `isViolation`, and `instanceDetails` carrying `instanceId`,
`instanceName`, `status`, `measuredHours`, `runningHours`, `uptimePercent`.

**Rules and their limits**

- `instanceDetails` exists so the figure can be **audited** rather than trusted: an
  operator seeing an unexpected violation can read `measuredHours` against
  `runningHours` per instance and see which one pulled the average down.
- Anchoring the window on `launchedAt` means a new instance is not penalised for the part
  of the month before it existed.
- The figure is an **approximation** — there is no status-history table. Only the most
  recent outage counts, the current outage is assumed to have started at the last update,
  and instances are weighted equally. Stated in full at
  [SLA § 3.1](../business-rules/SLA.md#31-what-the-approximation-gets-wrong); it is the
  reason [BRD § 7](BRD.md#7-known-shortfalls-against-these-requirements) records BR-13 as
  partially met.
- Not paginated: the average is taken across all instances, so a page would produce a
  different — and wrong — `uptimePercent`.

---

## Diagnosis

### F-DIAG-01 — Diagnose an instance

| | |
|---|---|
| **Endpoint** | `GET /api/instances/{id}/diagnosis` |
| **Realises** | FR-09, BR-16, BR-17 |
| **Verified by** | `diagnosis_falls_back_to_a_rule_based_answer`, `diagnosis_survives_a_provider_failure`, `diagnosis_works_for_a_healthy_instance_too` |

**Processing**

1. Load the instance and assert access (`404` / `403`).
2. Load its **10 most recent alerts**.
3. Release the database connection back to the pool *before* calling the provider, so a
   diagnosis in flight occupies none.
4. If an API key is configured, call the model with the instance metadata and those
   alerts, bounded at a 30-second timeout with at most one retry.
5. On any provider condition — no key, timeout, transport error, exception, empty answer —
   fall back to a deterministic rule-based write-up built from the same inputs.
6. Return the text with `source` set to `"llm"` or `"rule-based"`.

**Output** `200`

| Field | Type | Notes |
|---|---|---|
| `instanceId`, `instanceName` | int, string | |
| `status` | enum | Status at diagnosis time |
| `diagnosis` | string | Plain text: *Probable Causes* / *Recommended Actions* / *Prevention* |
| `source` | string | `"llm"` or `"rule-based"` |

**Errors** — `401` · `403` · `404`. **Never `5xx` for a provider problem** — a slow or
broken provider is a fallback, not a failure.

**Rules**

- The endpoint is not restricted to unhealthy instances; a healthy one gets a diagnosis
  too.
- The provider is fully isolated in one service. The controller never imports the SDK and
  receives only `(text, source)`, so changing provider or prompt touches nothing else.
- Worst-case latency is bounded by design at roughly one minute
  ([NFR-PERF-04](SRS.md#52-performance)).

---

## Related

| Document | Why |
|---|---|
| [SRS.md](SRS.md) | The requirement each function realises |
| [BRD.md](BRD.md) | The business need behind those requirements |
| [USE_CASES.md](USE_CASES.md) | The same functions as actor-driven scenarios |
| [../testing/TEST_CASES.md](../testing/TEST_CASES.md) | The cases that verify every rule above |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | The delivered request/response shapes |
| [../business-rules/](../business-rules/README.md) | The reasoning behind the subtle rules |
| [../manual/USER_MANUAL.md](../manual/USER_MANUAL.md) | The same functions written for the person using them |
