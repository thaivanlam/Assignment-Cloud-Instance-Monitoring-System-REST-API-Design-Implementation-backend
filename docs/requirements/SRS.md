# Software Requirements Specification

| | |
|---|---|
| System | TechValley Cloud Instance Monitoring System |
| Document | Software Requirements Specification (SRS) |
| Status | Baseline — describes the delivered system |
| Owner | TechValley Developer Track team |
| Last reviewed | 2026-09-01 |

Functional requirements, non-functional requirements (performance, security, interface)
and the technical constraints of the system. The business need behind them is
[BRD.md](BRD.md); the field-level behaviour of each function is [FRS.md](FRS.md).

**Contents** — [1 Introduction](#1-introduction) · [2 Overall description](#2-overall-description) ·
[3 External interfaces](#3-external-interface-requirements) ·
[4 Functional requirements](#4-functional-requirements) ·
[5 Non-functional requirements](#5-non-functional-requirements) ·
[6 Data requirements](#6-data-requirements) ·
[7 Verification](#7-verification) · [8 Traceability](#8-traceability) ·
[9 Open issues](#9-open-issues-and-known-limitations)

---

## 1. Introduction

### 1.1 Purpose

This document specifies what the software must do and how well it must do it, at the level
of detail a developer needs before writing code and a tester needs before writing test
cases. It is the middle document of three: business need ([BRD](BRD.md)) → software
requirements (this document) → function specification ([FRS](FRS.md)).

### 1.2 Scope of the software

A REST API that records the cloud instances TechValley operates for its client companies,
detects three trouble conditions, keeps an alert history, and reports cost, forecast and
SLA per client. It includes an AI-assisted diagnosis endpoint with a deterministic
fallback. It does **not** control real cloud infrastructure, send notifications, invoice,
or run scheduled jobs — see [BRD § 4.2](BRD.md#42-out-of-scope).

### 1.3 Definitions and abbreviations

Terms specific to the domain are in the [BRD glossary](BRD.md#13-glossary). Terms specific
to this document:

| Term | Meaning |
|---|---|
| **FR-nn** | A functional requirement in [§ 4](#4-functional-requirements) |
| **NFR-xxx-nn** | A non-functional requirement in [§ 5](#5-non-functional-requirements) |
| **Scope / scoping** | Restricting what a caller sees to the clients they are responsible for |
| **Scan** | One call to a monitoring endpoint, which both reads and records alerts |
| **Envelope** | The `PageResponse` wrapper — `items`, `total`, `page`, `size`, `totalPages` |
| **Member** | An authenticated staff account (`ADMIN` or `CLIENT_MANAGER`) |

### 1.4 References

| Reference | Contents |
|---|---|
| [BRD.md](BRD.md) | Business requirements this specification realises |
| [FRS.md](FRS.md) | Per-function detail for every FR below |
| [../api/](../api/README.md) | The delivered API reference — endpoints, conventions, errors |
| [../business-rules/](../business-rules/README.md) | The rules, with implementation notes and reasoning |
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | Realised architecture |
| [../design/ERD.md](../design/ERD.md) | Realised data model |
| [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) | Measurements behind the performance NFRs |
| [../security/SECURITY_BUGS.md](../security/SECURITY_BUGS.md) | Findings against the security NFRs |

---

## 2. Overall description

### 2.1 Product perspective

A standalone server application. It has no user interface of its own beyond the
interactive API documentation generated from the code, and no integration with a cloud
provider. One external dependency exists — the Anthropic API for diagnosis — and it is
**optional at runtime**: with no key configured, the system degrades to a deterministic
answer rather than failing.

```
Operator (Swagger UI / curl / client tool)
        │  HTTPS·JSON + Bearer JWT
        ▼
┌──────────────────────────────────────────────┐
│ FastAPI application                          │
│  controllers → services → models             │
│  core: JWT, scoping, domain exceptions       │
└───────────┬──────────────────────┬───────────┘
            │                      │ optional
            ▼                      ▼
     SQLite (monitoring.db)   Anthropic API
                              └─ unavailable → rule-based fallback
```

### 2.2 Product functions

| Group | Functions |
|---|---|
| Authentication | Log in, validate a token on every request, health check |
| Instance register | Register, list (filter/sort/page), read one, change status, delete |
| Monitoring | Three detection scans, one aggregate report |
| Alerts | History with filters, resolve |
| Clients | Register, list, list instances, cost, forecast, SLA |
| Diagnosis | AI-assisted incident write-up with deterministic fallback |

Nineteen endpoints plus a health check, catalogued in
[../api/OVERVIEW.md § 1](../api/OVERVIEW.md#1-endpoint-map).

### 2.3 User classes and characteristics

| User class | Technical level | Frequency | Privileges |
|---|---|---|---|
| Operations administrator | Comfortable with an API client | Daily | Everything, plus client registration |
| Client manager | Comfortable with an API client | Daily | Their own clients only |
| On-call engineer | Reads responses; rarely writes | Per incident | Same as their role |
| Integrating dashboard | Machine | Polls | Same as the account it authenticates as |

There is no anonymous user class. Only `GET /` and `POST /api/auth/login` are reachable
without a token.

### 2.4 Operating environment

| Item | Requirement |
|---|---|
| Runtime | Python 3.11+ (3.14 tested) |
| Framework | FastAPI with an ASGI server (uvicorn) |
| Database | SQLite by default; any SQLAlchemy-supported engine via `DATABASE_URL` |
| Client | Anything that speaks HTTP/1.1 and JSON |
| Deployment | Single process locally; also runs as a Vercel serverless function ([DEPLOYMENT](../operations/DEPLOYMENT.md)) |
| Network | Outbound HTTPS to `api.anthropic.com` **only if** the diagnosis feature is to use the model |

### 2.5 Design and implementation constraints

| ID | Constraint | Origin |
|---|---|---|
| **CON-01** | MVC layering: `models/` · `schemas/` · `controllers/`, with business logic in `services/` and auth in `core/` | Assignment structure ([ARCHITECTURE](../design/ARCHITECTURE.md)) |
| **CON-02** | All API and database field names are camelCase | Assignment specification; no translation layer exists |
| **CON-03** | Services raise domain exceptions, never `HTTPException`; controllers and handlers map them to status codes | Keeps the domain testable without a web client |
| **CON-04** | The schema is created from ORM metadata at startup; there are no migrations | Disposable SQLite file. A column change means recreating the database |
| **CON-05** | The system must run with no `.env` and no API key | [BRD § 9](BRD.md#9-constraints) |
| **CON-06** | Enum values cross the wire as uppercase names | Assignment specification |
| **CON-07** | Timestamps are ISO-8601 UTC from one shared `utcnow()` helper | Consistency between `launchedAt`, `updatedAt`, `detectedAt`, `resolvedAt` |

### 2.6 Assumptions and dependencies

- The assumptions in [BRD § 8](BRD.md#8-assumptions) hold.
- Instance state is supplied by callers; nothing is discovered from a cloud provider.
- `anthropic`, `fastapi`, `sqlalchemy`, `pydantic`, `pyjwt` are available at the versions
  pinned in [requirements.txt](../../requirements.txt).
- The demo data in [../demo/SEED_DATA.md](../demo/SEED_DATA.md) exists on a fresh
  database, and the test suite's expected values depend on it.

---

## 3. External interface requirements

### 3.1 User interfaces

| ID | Requirement |
|---|---|
| **UI-01** | The system shall publish interactive API documentation at `/docs` (Swagger UI) generated from the code, so every endpoint is callable from a browser with no client to install |
| **UI-02** | The machine-readable schema shall be available at `/openapi.json` |
| **UI-03** | Endpoints shall be grouped under the tags *Health, Auth, Instances, Monitoring, Alerts, Clients* so the surface is navigable by role rather than by URL |
| **UI-04** | Swagger UI shall accept a Bearer token through its **Authorize** control, so a whole session can be driven from the browser |

There is no other user interface. `UI-02` is a *disclosure* concern as well as a
convenience — see [NFR-SEC-06](#54-security).

### 3.2 API interface

| ID | Requirement |
|---|---|
| **API-01** | All requests and responses shall use `application/json`, UTF-8 |
| **API-02** | Field names shall be camelCase in both directions (CON-02) |
| **API-03** | Enum values shall be uppercase strings (CON-06) |
| **API-04** | Datetimes shall be ISO-8601 UTC without a timezone suffix, e.g. `2026-08-21T14:07:00` |
| **API-05** | Money shall be a `float` in USD, rounded to 2 decimals in aggregates |
| **API-06** | Percentages shall be `0.0–100.0`, not ratios; `uptimePercent` rounded to 3 decimals |
| **API-07** | Every list endpoint shall accept `page` and `size` and answer in the `PageResponse` envelope |
| **API-08** | Errors shall carry a human-readable `detail`; domain errors shall additionally carry a machine-readable `error` discriminator ([ERRORS § 2](../api/ERRORS.md#2-two-body-shapes)) |

### 3.3 Software interfaces

| Interface | Direction | Requirement |
|---|---|---|
| **SQLAlchemy / SQLite** | Outbound | The engine is selected from `DATABASE_URL`. For SQLite, `journal_mode=WAL` and `synchronous=NORMAL` shall be set on every connection so a writing scan does not lock out readers ([DATABASE](../design/DATABASE.md)) |
| **Anthropic API** | Outbound, optional | Used only by `GET /api/instances/{id}/diagnosis`. Bounded per [NFR-PERF-04](#52-performance). Any failure — missing key, timeout, error, malformed reply — shall be absorbed into the fallback path |
| **Environment / `.env`** | Inbound | All settings shall be readable from environment variables with working defaults ([CONFIGURATION](../operations/CONFIGURATION.md)) |

### 3.4 Communication interfaces

| ID | Requirement |
|---|---|
| **COM-01** | HTTP/1.1; the transport shall be HTTPS in any deployment outside localhost |
| **COM-02** | Authentication shall use the `Authorization: Bearer <jwt>` header |
| **COM-03** | The token shall be a JWT signed with HS256, carrying `sub`, `email`, `role` and `exp` |
| **COM-04** | No session cookie, server-side session store, or CSRF token is used — the API is stateless |

---

## 4. Functional requirements

Each FR is realised by one or more functions in the [FRS](FRS.md), where inputs,
processing rules, outputs and error paths are given in full.

### FR-01 — Authentication and session

| | |
|---|---|
| **The system shall** | Issue a signed token in exchange for a valid email and password, and require that token on every endpoint except the health check and login |
| **Detail** | Tokens are HS256 JWTs with a configurable lifetime (default 120 minutes) carrying `sub`, `email`, `role`, `exp`. The member row is re-read from the database on every request, so a deleted member's token stops working immediately. Login failures shall not reveal whether the email or the password was wrong |
| **Realised by** | [F-AUTH-01](FRS.md#f-auth-01--log-in), [F-AUTH-02](FRS.md#f-auth-02--authenticate-a-request), [F-AUTH-03](FRS.md#f-auth-03--health-check) |
| **Traces to** | BR-06 |

### FR-02 — Client company management

| | |
|---|---|
| **The system shall** | Let an administrator register a client company with a contract plan and exactly one responsible manager, and let any member list the clients they are entitled to see |
| **Detail** | `managerId` must reference an existing member **whose role is `CLIENT_MANAGER`**; pointing a client at an administrator is a business-rule failure (`400`), not a schema failure. Listing is scoped: an administrator sees all, a manager sees only their own — including in the envelope's `total` |
| **Realised by** | [F-CLNT-01](FRS.md#f-clnt-01--register-a-client), [F-CLNT-02](FRS.md#f-clnt-02--list-clients), [F-CLNT-03](FRS.md#f-clnt-03--list-a-clients-instances) |
| **Traces to** | BR-02, BR-05 |

### FR-03 — Instance register

| | |
|---|---|
| **The system shall** | Record cloud instances against a client, and list them with pagination, filtering and sorting |
| **Detail** | On registration the server derives `monthlyCost` from `instanceType` and stamps `launchedAt`; `monthlyCost` shall never be accepted from the request. Listing supports filters on `status`, `clientId`, `region`, `instanceType`, and a `sort` parameter with a `-` prefix for descending. Filters combine with `AND` and are applied **in addition to** role scoping, so no parameter can widen visibility |
| **Realised by** | [F-INST-01](FRS.md#f-inst-01--register-an-instance), [F-INST-02](FRS.md#f-inst-02--list-instances), [F-INST-03](FRS.md#f-inst-03--read-one-instance) |
| **Traces to** | BR-01, BR-03, BR-04 |

### FR-04 — Instance lifecycle

| | |
|---|---|
| **The system shall** | Let a member change an instance's status and CPU reading, and delete an instance that is not running |
| **Detail** | Any status may move to any other — there is no state machine. Moving to `STOPPED` or `ERROR` without an explicit CPU value resets CPU to `0.0`. An update that changes neither status nor CPU is a no-op and **shall not** move `updatedAt`. Deleting a `RUNNING` instance shall be refused with `409`. Deleting any other instance removes its alerts with it |
| **Realised by** | [F-INST-04](FRS.md#f-inst-04--update-status), [F-INST-05](FRS.md#f-inst-05--delete-an-instance) |
| **Traces to** | BR-14, BR-15 |

### FR-05 — Detection and reporting

| | |
|---|---|
| **The system shall** | Detect and return (a) running instances at or above the CPU threshold, (b) instances in `ERROR`, (c) instances stopped for at least the idle threshold, and produce one aggregate report of the estate |
| **Detail** | Each scan records an alert for **every** instance meeting its condition, not only the ones on the page returned — pagination bounds the response, never the detection. The report is read-only and creates no alerts. Its `instanceCountByStatus` is zero-filled for all three statuses; `totalMonthlyCost` covers instances of every status; `unresolvedAlertCount` is a true count while the embedded `unresolvedAlerts` array is capped at the 20 most recent |
| **Realised by** | [F-MON-01](FRS.md#f-mon-01--scan-for-high-cpu-instances), [F-MON-02](FRS.md#f-mon-02--scan-for-failed-instances), [F-MON-03](FRS.md#f-mon-03--scan-for-long-stopped-instances), [F-MON-04](FRS.md#f-mon-04--aggregate-monitoring-report) |
| **Traces to** | BR-07, BR-10 |

### FR-06 — Alert lifecycle

| | |
|---|---|
| **The system shall** | Record one open alert per instance per condition, keep a filterable history, and let a member mark an alert resolved |
| **Detail** | Before inserting, a scan shall skip any instance that already has an **unresolved** alert of that type — the uniqueness is on the open alert, not on the pair, so resolving frees the slot and the next scan may open a fresh alert if the condition persists. Resolution is manual; nothing auto-resolves. Re-resolving is a no-op that preserves the original `resolvedAt`. History is ordered newest first with a unique tiebreaker so pages partition the set exactly |
| **Realised by** | [F-ALRT-01](FRS.md#f-alrt-01--list-alert-history), [F-ALRT-02](FRS.md#f-alrt-02--resolve-an-alert) |
| **Traces to** | BR-08, BR-09 |

### FR-07 — Cost and forecast

| | |
|---|---|
| **The system shall** | Report a client's current-month cost across instances of every status, and forecast next month from currently running instances only |
| **Detail** | Unit prices are SMALL `$50` / MEDIUM `$120` / LARGE `$250` per month. The current cost returns a per-instance breakdown carrying each instance's status. The forecast groups running instances by type and reports count, unit price and subtotal per type; types with no running instance are absent rather than zero. `forecastMonth` rolls the year correctly in December. Neither response is paginated, because both compute over all of the client's instances |
| **Realised by** | [F-CLNT-04](FRS.md#f-clnt-04--current-month-cost), [F-CLNT-05](FRS.md#f-clnt-05--next-month-cost-forecast) |
| **Traces to** | BR-11, BR-12 |

### FR-08 — SLA reporting

| | |
|---|---|
| **The system shall** | Report a client's uptime for the current month against its contract plan's threshold, and flag a violation |
| **Detail** | Thresholds are PREMIUM `99.9` / STANDARD `99.0` / BASIC `95.0`. The measurement window starts at the later of the month's first day and the instance's `launchedAt`, so a new instance is not penalised for time before it existed. A running instance counts as up for the whole window; a stopped or failed one counts as up until its last status change. The client figure is the mean across its instances, and a client with no instances reports `100.0` with no violation. The response shall expose `measuredHours` and `runningHours` per instance so the figure can be audited. The approximation's limits shall be documented, not hidden |
| **Realised by** | [F-CLNT-06](FRS.md#f-clnt-06--sla-uptime) |
| **Traces to** | BR-13 |

### FR-09 — AI-assisted diagnosis

| | |
|---|---|
| **The system shall** | Return a written incident diagnosis for one instance — probable causes, recommended actions, prevention — from an LLM where one is reachable, and from deterministic rules otherwise |
| **Detail** | Context is the instance's metadata plus its 10 most recent alerts. The response shall name its origin in a `source` field (`"llm"` or `"rule-based"`). No provider condition — absent key, timeout, transport error, empty answer — may produce a `5xx`. The endpoint shall work for a healthy instance too |
| **Realised by** | [F-DIAG-01](FRS.md#f-diag-01--diagnose-an-instance) |
| **Traces to** | BR-16, BR-17 |

### FR-10 — Cross-cutting behaviour

| | |
|---|---|
| **The system shall** | Apply one pagination convention, one scoping rule and one error-mapping scheme across every endpoint |
| **Detail** | `page ≥ 1`, `size 1–100` (default 10), one `PageResponse` envelope, `total` counted after filters and scoping. Scoping is applied by filtering the query for list endpoints and by checking after load for single resources. Domain exceptions map to `400/403/404/409`; schema failures produce `422` |
| **Realised by** | [F-X-01](FRS.md#f-x-01--pagination), [F-X-02](FRS.md#f-x-02--role-scoping), [F-X-03](FRS.md#f-x-03--error-mapping) |
| **Traces to** | BR-03, BR-18 |

---

## 5. Non-functional requirements

### 5.1 Priority key

**M** = must hold for the system to be considered delivered · **S** = should hold ·
**V** = verified by the automated suite · **D** = verified by a documented measurement or
review.

### 5.2 Performance

| ID | Requirement | Pri | Basis |
|---|---|:--:|---|
| **NFR-PERF-01** | No endpoint's work shall grow with the size of a table it does not need to read. Every column the API filters or sorts on shall be indexed | M · D | [PERF-04](../performance/PERFORMANCE_BUGS.md#perf-04), [ERD § Indexes](../design/ERD.md#indexes) |
| **NFR-PERF-02** | The connection pool shall serve the framework's full request concurrency. With 40 threadpool workers the pool is sized 20 + 20 overflow, with `pool_pre_ping` enabled | M · D | [PERF-02](../performance/PERFORMANCE_BUGS.md#perf-02) |
| **NFR-PERF-03** | No response shall grow without bound. All seven list endpoints paginate at `size ≤ 100`; the report's embedded alert array is capped at 20 | M · V | [PERF-07](../performance/PERFORMANCE_BUGS.md#perf-07), [CONVENTIONS § 1](../api/CONVENTIONS.md#1-pagination) |
| **NFR-PERF-04** | A diagnosis shall be bounded: 30-second provider timeout with at most one retry, so the endpoint answers in about a minute in the worst case | M · D | [PERF-03](../performance/PERFORMANCE_BUGS.md#perf-03) |
| **NFR-PERF-05** | A request waiting on the LLM shall hold no database connection | M · D | [PERF-03](../performance/PERFORMANCE_BUGS.md#perf-03), [ARCHITECTURE § 5](../design/ARCHITECTURE.md#connection-pool) |
| **NFR-PERF-06** | A monitoring scan that records nothing shall not write, so repeated polling does not take a database-wide lock | M · D | [PERF-01](../performance/PERFORMANCE_BUGS.md#perf-01) |
| **NFR-PERF-07** | The statement count of a scan shall not grow with the number of rows it returns; dedup shall be one query per scan, not two per instance | S · D | [PERF-05](../performance/PERFORMANCE_BUGS.md#perf-05), [PERF-06](../performance/PERFORMANCE_BUGS.md#perf-06) |
| **NFR-PERF-08** | A scan shall bound its memory by walking the matching set in id batches (`ID_BATCH_SIZE`, 500) while still detecting over the whole set | S · V | [ALERTING § 2](../business-rules/ALERTING.md#2-detection-writes-alerts) |

### 5.3 Capacity

| ID | Requirement | Pri |
|---|---|:--:|
| **NFR-CAP-01** | The design target is the low thousands of instances and tens of thousands of alerts on one SQLite file. Beyond that, `DATABASE_URL` should point at a server engine | S |
| **NFR-CAP-02** | `size` shall be capped at 100 rows per page on every listing | M |
| **NFR-CAP-03** | The `alerts` table is the fastest-growing table and is never pruned; every path that reads it shall be bounded (paged listing, capped report array) | M |

### 5.4 Security

| ID | Requirement | Pri | Status |
|---|---|:--:|---|
| **NFR-SEC-01** | Passwords shall be stored as salted PBKDF2-SHA256 hashes (260,000 iterations), never in plaintext or reversibly | M · V | Met |
| **NFR-SEC-02** | Authorization shall be enforced on every endpoint from the member row loaded per request, not from a claim the client sends | M · V | Met |
| **NFR-SEC-03** | Login shall not reveal whether the email or the password was wrong | M · V | Met |
| **NFR-SEC-04** | The system shall not be vulnerable to SQL injection; all queries shall be built through the ORM with bound parameters, and any user-supplied identifier used for ordering shall be whitelisted | M · D | Met and reviewed — [SECURITY_BUGS](../security/SECURITY_BUGS.md) |
| **NFR-SEC-05** | No stack trace or internal detail shall reach a client | M · D | Met |
| **NFR-SEC-06** | The signing key shall be deployment-specific, and no credential shall be discoverable through the API | M | **Not met** — [SEC-01, SEC-02](../security/SECURITY_BUGS.md) |
| **NFR-SEC-07** | An issued token shall be revocable before expiry | S | **Not met** — [SEC-04](../security/SECURITY_BUGS.md), blocked on SEC-08 |
| **NFR-SEC-08** | Transport shall be HTTPS outside localhost | M | Deployment responsibility — [DEPLOYMENT](../operations/DEPLOYMENT.md) |

NFR-SEC-06 and NFR-SEC-07 are recorded as **not met** deliberately. The security review
reproduced 15 findings and fixed none of them; the register is the plan of record, and
this specification does not claim what the code does not do.

### 5.5 Reliability and availability

| ID | Requirement | Pri |
|---|---|:--:|
| **NFR-REL-01** | An optional external service shall never cause a request to fail. The diagnosis endpoint shall return `200` with a rule-based answer on any provider condition | M · V |
| **NFR-REL-02** | Startup shall be idempotent: creating tables, creating any missing index, and seeding shall all be safe to repeat on an existing database | M · V |
| **NFR-REL-03** | Seeding shall never duplicate rows or overwrite a changed password | M · V |
| **NFR-REL-04** | A repeated write that changes nothing shall be a no-op — a re-resolved alert keeps its original `resolvedAt`, a no-change status update keeps its original `updatedAt` | M · V |
| **NFR-REL-05** | Deleting an instance shall not leave an alert pointing at a missing instance | M · V |
| **NFR-REL-06** | Pages shall partition a result set exactly — no row on two pages, none missing — for every supported sort | M · V |

### 5.6 Maintainability

| ID | Requirement | Pri |
|---|---|:--:|
| **NFR-MNT-01** | Layer boundaries shall hold: no business rule in a controller, no HTTP vocabulary in a service, no database access in a schema (CON-01, CON-03) | M |
| **NFR-MNT-02** | Every threshold, price and lifetime shall be a setting, not a literal in a rule | M |
| **NFR-MNT-03** | Pagination bounds, the envelope and the counting shall exist in exactly one module | M |
| **NFR-MNT-04** | A behaviour change shall update its document in the same commit, checked by a commit-time reminder | M |
| **NFR-MNT-05** | The functional suite shall drive the API over HTTP against a per-test database, with the provider call the only stub | M · V |

### 5.7 Portability

| ID | Requirement | Pri |
|---|---|:--:|
| **NFR-POR-01** | The engine, pool class and SQLite pragmas shall be selected from `DATABASE_URL`, so a non-SQLite target needs no code change | S |
| **NFR-POR-02** | The application shall run on Windows, Linux and macOS, and as a serverless function | S |
| **NFR-POR-03** | The system shall start with no `.env` present, on defaults alone | M · V |

### 5.8 Usability

| ID | Requirement | Pri |
|---|---|:--:|
| **NFR-USE-01** | Every endpoint shall be callable from Swagger UI without a separate client, and grouped by tag | M |
| **NFR-USE-02** | Every error shall carry a human-readable `detail` that names the resource and the reason, e.g. `Instance 1 is RUNNING and cannot be deleted. Stop it first.` | M · V |
| **NFR-USE-03** | Alert messages shall embed the reading that triggered them, so the history is readable without cross-referencing | M · V |
| **NFR-USE-04** | An out-of-range page shall answer `200` with an empty `items` array rather than an error | M · V |

### 5.9 Compliance

| ID | Requirement | Pri |
|---|---|:--:|
| **NFR-COM-01** | The project is MIT-licensed; dependencies shall be compatible with redistribution | M |
| **NFR-COM-02** | Documentation shall be written in English regardless of the working language of the team | M |
| **NFR-COM-03** | No personal data beyond staff name and email is stored; demo credentials are non-secret by design and are documented as such | M |

---

## 6. Data requirements

### 6.1 Entities

Five tables — `members`, `clients`, `instances`, `alerts`, `cost_snapshots` — specified
in [../design/ERD.md](../design/ERD.md).

| ID | Requirement |
|---|---|
| **DAT-01** | `members.email` shall be unique; it is the login identifier |
| **DAT-02** | Every client shall reference exactly one member as its manager |
| **DAT-03** | Every instance shall reference exactly one client |
| **DAT-04** | Every alert shall reference exactly one instance, and shall be deleted with it |
| **DAT-05** | `instances.monthlyCost` shall be derived at registration and **stored**, so a later price change does not rewrite history |
| **DAT-06** | `instances.updatedAt` shall record the moment of the last actual status or CPU change, and nothing else may move it |
| **DAT-07** | `cost_snapshots` shall hold one `(clientId, snapshotMonth)` row per client-month; the month is a `YYYY-MM` string |
| **DAT-08** | `alerts.isResolved` plus `resolvedAt` shall carry the open/closed state that the dedup rule reads |

### 6.2 Retention and integrity

| ID | Requirement |
|---|---|
| **DAT-09** | There is no archival or pruning policy; the alert history grows until an instance is deleted |
| **DAT-10** | Deleting an instance is permanent and takes its alerts with it — there is no soft delete |
| **DAT-11** | All timestamps shall come from one UTC helper so they are comparable across tables |
| **DAT-12** | The schema is created from ORM metadata; missing indexes shall be created at startup against an existing file (CON-04) |

---

## 7. Verification

How each class of requirement is checked, and by what.

| Requirement class | Verification method | Evidence |
|---|---|---|
| Functional (FR-01…FR-10) | Automated functional tests over HTTP against a seeded in-memory database | [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md), [../testing/TEST_CASES.md](../testing/TEST_CASES.md) |
| Field-level behaviour | Same suite, asserting exact values (`$2,100`, warnings on instances 1/4/11/14) | [../demo/SEED_DATA.md](../demo/SEED_DATA.md) |
| Performance NFRs | Measured review, 15 findings with before/after figures and query plans | [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) |
| Security NFRs | Reproduced review against the running API with unmodified application code | [../security/SECURITY_BUGS.md](../security/SECURITY_BUGS.md) |
| Interface (UI/API) | Swagger UI captures taken against a freshly seeded server | [../screenshots/README.md](../screenshots/README.md) |
| Operability | Deployment, configuration and 15 incident runbooks | [../operations/](../operations/README.md) |
| Maintainability | Layering rules plus a commit-time documentation check | [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md) |

Requirements marked **D** in [§ 5](#5-non-functional-requirements) are verified by a
document, not by a test: the suite does not measure latency, and it does not attempt to
forge a token. That split is stated so no reader assumes a green test run has verified the
performance and security NFRs.

---

## 8. Traceability

| FR | Business requirement | Functions | Test suites |
|---|---|---|---|
| FR-01 | BR-06 | F-AUTH-01…03 | `test_auth.py` |
| FR-02 | BR-02, BR-05 | F-CLNT-01…03 | `test_clients.py` |
| FR-03 | BR-01, BR-03, BR-04 | F-INST-01…03 | `test_instances.py` |
| FR-04 | BR-14, BR-15 | F-INST-04, F-INST-05 | `test_instances.py`, `test_member_c.py` |
| FR-05 | BR-07, BR-10 | F-MON-01…04 | `test_member_c.py` |
| FR-06 | BR-08, BR-09 | F-ALRT-01, F-ALRT-02 | `test_alerts.py` |
| FR-07 | BR-11, BR-12 | F-CLNT-04, F-CLNT-05 | `test_clients.py` |
| FR-08 | BR-13 | F-CLNT-06 | `test_clients.py` |
| FR-09 | BR-16, BR-17 | F-DIAG-01 | `test_diagnosis.py` |
| FR-10 | BR-03, BR-18 | F-X-01…03 | every suite |

Requirement-to-test-case traceability is in
[../testing/TEST_CASES.md § 9](../testing/TEST_CASES.md#9-traceability-matrix).

---

## 9. Open issues and known limitations

| # | Issue | Consequence | Where it is tracked |
|---|---|---|---|
| 1 | SLA uptime is approximated from one timestamp | The figure is indicative, not contractual | [SLA § 3.1](../business-rules/SLA.md#31-what-the-approximation-gets-wrong) |
| 2 | Detection is triggered by a `GET`, which writes | Not REST-idiomatic; a caching proxy in front of the API would silently disable detection | [ALERTING § 2](../business-rules/ALERTING.md#2-detection-writes-alerts) |
| 3 | Two different error body shapes | A client must read `detail` first and treat `error` as optional | [ERRORS § 2](../api/ERRORS.md#2-two-body-shapes) |
| 4 | No migrations | A column change means recreating the database file | [ARCHITECTURE § 5](../design/ARCHITECTURE.md#5-startup) |
| 5 | `cost_snapshots` is written but never read | No month-over-month reporting | [COST § 6](../business-rules/COST.md#6-cost_snapshots) |
| 6 | `403` rather than `404` across scope | Confirms a resource exists to a caller who may not read it | [AUTHORIZATION § 3](../business-rules/AUTHORIZATION.md#3-403-rather-than-404) |
| 7 | 15 open security findings, two critical | The system is not ready for exposure outside a trusted network | [SECURITY_BUGS](../security/SECURITY_BUGS.md) |
| 8 | Concurrency is untested | The dedup check is read-then-write and is not exercised under parallel calls | [FUNCTIONAL_TESTS § 7](../testing/FUNCTIONAL_TESTS.md#7-what-is-deliberately-not-covered) |

---

## 10. Related

| Document | Why |
|---|---|
| [BRD.md](BRD.md) | The business need behind every FR |
| [FRS.md](FRS.md) | Field-level specification of each function named above |
| [USE_CASES.md](USE_CASES.md) | The same requirements as actor-driven scenarios |
| [../testing/TEST_CASES.md](../testing/TEST_CASES.md) | The cases that verify these requirements |
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | How the constraints in § 2.5 are realised |
| [../api/](../api/README.md) | The delivered interface described in § 3 |
