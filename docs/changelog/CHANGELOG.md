# Changelog

Every change to this repository that a reader would notice — new endpoints, changed
behaviour, fixed bugs, new documents — in reverse chronological order.

The project has no version tags. Entries are grouped by the date the work landed and
named after what that day's work accomplished, newest first. Each bullet cites the commit
that carries it, so `git show <hash>` always leads to the diff.

Categories follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/): **Added**,
**Changed**, **Fixed**, **Removed**, **Documentation**.

---

## At a glance

| Date | Milestone | Highlights |
|---|---|---|
| [2026-09-01](#2026-09-01--screenshots-follow-the-api) | Screenshots follow the API | Swagger captures are re-taken in the commit that invalidates them |
| [2026-09-01](#2026-09-01--database-engine-document) | Database engine document | Which pool each `DATABASE_URL` gets, and where in-memory SQLite is used |
| [2026-08-31](#2026-08-31--perf-02-fixed-the-connection-pool-matches-the-request-concurrency) | PERF-02 fixed | The pool serves 40 concurrent requests instead of 15 |
| [2026-08-31](#2026-08-31--perf-01-fixed-monitoring-polls-no-longer-lock-the-database) | PERF-01 fixed | Scans commit only when they record; SQLite runs in WAL |
| [2026-08-31](#2026-08-31--onboarding-path-and-change-history) | Onboarding path and change history | A reading order through `app/`, and this changelog |
| [2026-08-31](#2026-08-31--readme-as-a-landing-page) | README as a landing page | Badge header, architecture diagram, screenshot gallery |
| [2026-08-29](#2026-08-29--performance-review) | Performance review | 15 measured findings, three critical |
| [2026-08-25](#2026-08-25--vercel-deployment) | Vercel deployment | `vercel.json` serverless config |
| [2026-08-21](#2026-08-21--documentation-set-and-full-test-coverage) | Documentation set + full test coverage | Nine-folder `docs/` tree, 104 functional tests |
| [2026-08-15](#2026-08-15--agent-instructions) | Agent instructions | `CLAUDE.md`, `.claude/settings.json` |
| [2026-08-10](#2026-08-10--dead-import-cleanup) | Dead-import cleanup | Unused imports dropped from `client_service.py` |
| [2026-08-07](#2026-08-07--llm-key-fix-and-swagger-capture) | LLM key fix + Swagger capture | Diagnosis reached the API; 29 screenshots automated |
| [2026-08-02](#2026-08-02--llm-feature-write-up) | LLM feature write-up | Prompt design, implementation, sample output |
| [2026-08-01](#2026-08-01--client-validation-and-cascade-delete) | Client validation + cascade delete | `400` on a non-manager `managerId` |
| [2026-07-31](#2026-07-31--monitoring-module-completed) | Monitoring module completed | Idempotent status update, deterministic ordering |
| [2026-07-11](#2026-07-11--initial-codebase) | Initial codebase | 19 endpoints, 5 tables, MVC layout |

---

## 2026-09-01 — Screenshots follow the API

One commit adding a documentation rule. No source changed.

### Documentation

- **Added rule 6, *Screenshots follow the API*, to
  [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md#6-screenshots-follow-the-api)**
  — the 29 captures in [../screenshots/](../screenshots/README.md) are live Swagger UI
  responses, so a change to a route, a field, a status code, an error body or the seed
  numbers makes one wrong. The affected PNG is now re-captured in the *same commit* as
  the change, the same requirement rule 3 places on documents. The rule names the command
  (`python scripts/capture_swagger_ui.py --only <scenario>` against a running server),
  the `monitoring.db` side effects that make a full run drift from
  [../demo/SEED_DATA.md](../demo/SEED_DATA.md), and what to update when a scenario is
  added or removed. *Writing style* and *Related* renumbered to 7 and 8; the § 5 mapping
  anchor cited elsewhere in this file is unchanged.
- **Extended the source → document mapping** with a row for anything visible in a Swagger
  response, pointing at [../screenshots/](../screenshots/README.md).
- **Condensed the rule into [../../CLAUDE.md](../../CLAUDE.md)** as rule 5, so an agent
  gets it without opening the contributing guide.
- **Added a *Keeping them current* section to
  [../screenshots/README.md](../screenshots/README.md)** with the capture command, so the
  rule is discoverable from the folder it governs.
- **Listed the rule in the two conventions summaries** — [../README.md](../README.md)
  § *Conventions for these documents* and
  [../contributing/README.md](../contributing/README.md) § *The short version* — which
  would otherwise describe an incomplete rule set.

---

## 2026-09-01 — Database engine document

One commit adding documentation only. No source changed.

### Documentation

- **Added [../design/DATABASE.md](../design/DATABASE.md)** — where `DATABASE_URL` comes
  from, which pool class SQLAlchemy picks per URL (`QueuePool` for a file,
  `SingletonThreadPool` for in-memory), and why passing `pool_size`/`max_overflow` to the
  latter is a `TypeError` at import — the reason `IS_MEMORY_SQLITE` exists in
  [../../app/database.py](../../app/database.py). It answers *where in-memory SQLite is
  actually used*: only the `api` fixture in [../../tests/conftest.py](../../tests/conftest.py),
  which overrides the pool with `StaticPool` so the test thread and FastAPI's worker
  thread share one database instead of getting one empty database each. It also records
  what that mode gives up — no pool sizing, no WAL (`PRAGMA journal_mode=WAL` returns
  `memory`), no persistence, no sharing across processes — and that running the
  application itself on `sqlite:///:memory:` imports cleanly and then fails the first
  request with `no such table: members`, because the schema is created on the main thread
  and every handler runs in a worker thread with its own connection.
- **Linked from** [../design/README.md](../design/README.md),
  [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) § 5,
  [../testing/README.md](../testing/README.md),
  [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) § 2,
  [../README.md](../README.md) and the root [README.md](../../README.md).
- **Extended the source → document mapping** in
  [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md#5-source--document-mapping)
  with a row for `app/database.py`, which had none.

---

## 2026-08-31 — PERF-02 fixed: the connection pool matches the request concurrency

The second performance finding closed. Configuration only — no API contract changed, no
endpoint was added, and all 104 tests pass unchanged.

### Fixed

- **The database connection pool is sized to the request concurrency.** Every controller
  is synchronous, so FastAPI runs it in AnyIO's threadpool, which allows 40 workers at
  once, while `get_db` holds a connection for the whole request. The engine took
  SQLAlchemy's `QueuePool` defaults — 5 connections plus 10 overflow — so from the 16th
  concurrent request onward the surplus waited 30 seconds in `pool.connect()` and then
  failed with a 500. `app/database.py` now derives the pool from that same limit:
  `MAX_CONCURRENT_REQUESTS = 40`, split into `pool_size=20` and `max_overflow=20`, plus
  `pool_pre_ping=True` so a connection closed at the other end is replaced rather than
  handed out ([../../app/database.py](../../app/database.py)). Measured with 40 threads
  each holding a connection for 3 seconds: 15 of 40 served before, 40 of 40 after.
  The sizing is skipped for an in-memory SQLite URL, whose `SingletonThreadPool` has no
  overflow to configure.

Deliberately not done: capping the threadpool at 15 to match the old pool, the other half
of the choice offered in
[../performance/PERFORMANCE_BUGS.md § PERF-02](../performance/PERFORMANCE_BUGS.md#perf-02).
It would have made the connection pool the ceiling on concurrency for every endpoint,
including those that barely touch the database. The finding's remaining edge — a handler
that holds a connection for minutes, such as the LLM diagnosis — is
[PERF-03](../performance/PERFORMANCE_BUGS.md#perf-03) and is still open.

### Documentation

- [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) — PERF-02 marked
  **Fixed**, with what landed, what it does not fix, and the measurement behind the
  before/after table; the pool-exhaustion method added to § How these were measured.
- [../performance/README.md](../performance/README.md),
  [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) (new *Connection pool* section) and
  [../onboarding/READING_ORDER.md](../onboarding/READING_ORDER.md) updated to match.

---

## 2026-08-31 — PERF-01 fixed: monitoring polls no longer lock the database

The first performance finding to be closed since the review landed on 2026-08-29. No API
contract changed and no endpoint was added — all 104 tests pass unchanged.

### Fixed

- **A monitoring scan commits only when it recorded an alert.** `check_warnings`,
  `check_errors` and `check_long_stopped` called `db.commit()` unconditionally, including
  on the repeat polls where the dedup guard had inserted nothing. They now collect what
  `_record_alert` returns and pass it to the new `_commit_if_recorded`
  ([../../app/services/monitor_service.py](../../app/services/monitor_service.py)).
  Measured over one scan plus ten repeat polls of each endpoint: 11 commits each before,
  1 each after. The auto-record-on-scan behaviour documented in
  [../business-rules/ALERTING.md](../business-rules/ALERTING.md) is unchanged — a scan
  that finds something new still writes it.
- **SQLite connections run in WAL mode with `synchronous=NORMAL`**, set by
  `_set_sqlite_pragmas` on the engine's `connect` event
  ([../../app/database.py](../../app/database.py)). Under the previous rollback journal a
  write locked the whole database file and fsynced on commit, so every writing poll
  stalled every concurrent reader. The hook is skipped for a non-SQLite `DATABASE_URL`.
- **`.gitignore`** extended with `monitoring.db-wal` and `monitoring.db-shm`, the sidecar
  files WAL keeps beside the database.

Deliberately not done: moving alert recording off the read path onto a
`POST /api/monitor/scan` or a background task, the third fix
[../performance/PERFORMANCE_BUGS.md § PERF-01](../performance/PERFORMANCE_BUGS.md#perf-01)
proposed. It would add an endpoint and drop the auto-record-on-scan design, both out of
scope. The reasoning is recorded in that finding.

### Documentation

- **[../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md)** — the
  summary table gained a **Status** column, PERF-01 gained a "the fix that landed" section
  with the before/after commit counts, and the measurement method now covers how those
  counts were taken.
- **[../business-rules/ALERTING.md](../business-rules/ALERTING.md)** — § 2 states the
  commit-only-when-recorded rule and why it is invisible through the API.
- **[../design/ARCHITECTURE.md](../design/ARCHITECTURE.md)** — a "SQLite connection
  settings" subsection under Startup.
- **[../onboarding/READING_ORDER.md](../onboarding/READING_ORDER.md)** — two new stops for
  the two new functions, 75 → 77, with the numbering and cited line numbers carried
  through.

---

## 2026-08-31 — Onboarding path and change history

Two commits adding documentation only. No source changed.

### Documentation

- **Added `docs/onboarding/`** — [READING_ORDER.md](../onboarding/READING_ORDER.md), a
  guided path through all 17 source files under `app/`: 10 stages, 75 numbered stops,
  ordered so that no function is read before the things it calls. About 2–3 hours end to
  end, ~40 minutes for the first five stages. The root README had linked this file since
  `690bf28`; until now the folder did not exist. `c55ae05`
- **Extended the source → document mapping** in
  [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md#5-source--document-mapping)
  with a row for adding, removing, renaming or moving a function under `app/**` — the
  reading order cites line numbers, so it goes stale silently otherwise. `c55ae05`
- **Added `docs/changelog/`** — this document, covering every noticeable change since the
  initial commit on 2026-07-11, and a mapping row making it the document that every
  reader-visible change updates. Entries are grouped by date rather than by version,
  because the project carries no tags.

---

## 2026-08-31 — README as a landing page

Three commits reworking the root [README.md](../../README.md) only. No source changed.

### Documentation

- **Badge header and highlights table** — technology and status badges, each linking to
  the document behind its claim: auth, data model, LLM feature, 104 tests, 19 endpoints
  plus health. `b7b89d3`
- **Architecture diagram and a wider quick start** — the request path through the MVC
  layers drawn out, and the quick start extended to cover the `.env` file, the seeded
  database, and where Swagger lives. `9b7202b`
- **Screenshot gallery, sections reordered** — four representative Swagger captures
  inline, and the sections resequenced so a first-time reader meets the demo before the
  reference material. `690bf28`

---

## 2026-08-29 — Performance review

### Documentation

- **Added [performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md)** — 15
  findings ranked by severity, each with cause, measured evidence, and a fix; a suggested
  order of work; and the measurement method, so every figure is reproducible against the
  seeded database. Three are rated critical: `GET /api/monitor/*` writing and committing
  under SQLite's rollback journal (PERF-01), 40 threadpool workers against a connection
  pool of 15 (PERF-02), and the untimed LLM call inheriting the SDK's 600-second read
  timeout (PERF-03). `39c432f`
- **Indexed the new folder** from [../README.md](../README.md) and the root
  [README.md](../../README.md). `700854e`

Nothing here is a functional defect — the suite passes and the API returns correct answers
throughout. No fix was applied that day; the findings were recorded, not resolved. PERF-01
was fixed two days later — see
[2026-08-31 — PERF-01 fixed](#2026-08-31--perf-01-fixed-monitoring-polls-no-longer-lock-the-database).

---

## 2026-08-25 — Vercel deployment

### Added

- **`vercel.json`** — a `@vercel/python` build over `app/main.py` with every route
  rewritten to it, so the app runs as a serverless function. `2bf8310`
- **`.gitignore`** extended for the deployment artefacts. `2bf8310`

---

## 2026-08-21 — Documentation set and full test coverage

The largest change in the project's history: `docs/` grew from three loose files into a
nine-folder tree, and the test suite grew from one member's scope to every endpoint.

### Added

- **Functional tests for every endpoint** — `test_auth.py`, `test_instances.py`,
  `test_clients.py`, `test_alerts.py` and `test_diagnosis.py`, joining the existing
  `test_member_c.py`. The suite drives the API over HTTP against a per-test in-memory
  database seeded with the same demo data, so its expected values are exact. 104 tests, no
  API key required — the diagnosis tests assert the fallback path. `bfba278`

### Removed

- **`test.md` and `test.txt`** — scratch files left behind by earlier branch
  experiments. `13aabcd`

### Documentation

- **[api/](../api/README.md)** — `OVERVIEW.md`, `AUTHENTICATION.md`, `CONVENTIONS.md`,
  `ERRORS.md`, and a per-endpoint `ENDPOINTS.md`. `5b07b79`
- **[business-rules/](../business-rules/README.md)** — authorization, instance lifecycle,
  alerting, cost and SLA extracted into one document each, stating the rule and why it
  exists. `65a5297`
- **[demo/](../demo/README.md)** — demo accounts, seed data, and a 29-step
  walkthrough. `d2439d3`
- **[design/ARCHITECTURE.md](../design/ARCHITECTURE.md)** — MVC layering, request flow,
  configuration. `762c112`
- **[testing/](../testing/README.md)** — `FUNCTIONAL_TESTS.md` (approach, fixtures, suite
  catalogue, coverage, known gaps) and `RUNNING_TESTS.md` (install, run, select a test,
  read a failure). `bfba278`
- **[contributing/](../contributing/README.md)** — `COMMITS.md` and `DOCUMENTATION.md`,
  including the source → document mapping that `CLAUDE.md` now defers to rather than
  duplicating. `3573d46`, `c0f7d45`
- **Moved `ERD.md` and `LLM_FEATURE.md` into `design/`, `MEMBER_C.md` into `team/`**, each
  folder given a README. `962753f`
- **Indexed the Swagger screenshots** captured on 2026-08-07. `68dde5e`
- **Added the top-level documentation index** [../README.md](../README.md) and rewrote the
  root [README.md](../../README.md) as a landing page. `e92f22c`, `2b9241f`

---

## 2026-08-15 — Agent instructions

### Added

- **[CLAUDE.md](../../CLAUDE.md)** — project summary, MVC layout table, run and test
  commands, and the reference-docs policy for FastAPI, Pydantic v2 and SQLAlchemy 2.0.
- **`.claude/settings.json`** — tooling permissions. `25ed339`

---

## 2026-08-10 — Dead-import cleanup

### Changed

- **`app/services/client_service.py`** — dropped the unused `calendar` and `datetime`
  imports. No behaviour change. `53ac164`

---

## 2026-08-07 — LLM key fix and Swagger capture

### Fixed

- **The diagnosis endpoint never saw the configured API key.** The `anthropic` SDK reads
  `ANTHROPIC_API_KEY` from the process environment only, so the value `pydantic-settings`
  loaded out of `.env` never reached it, and diagnosis silently fell back on every
  deployment configured that way. The key is now handed to the client explicitly, with the
  SDK's own credential resolution kept as the fallback when nothing is
  configured. `9af4251`
- **Truncated or empty diagnoses.** Adaptive thinking spends thinking tokens from the same
  `max_tokens` budget as the answer, so the 1024 cap could be consumed entirely by
  thinking. Raised to 16000, with a warning logged when the cap is still hit. `9af4251`

### Added

- **`scripts/capture_swagger_ui.py`** — a Playwright script that drives Swagger UI through
  all 29 API scenarios and captures each response. `033393d`
- **29 Swagger UI screenshots** under [screenshots/](../screenshots/README.md), covering
  the happy paths, the role-scoped views, and the `401` / `403` / `404` / `409`
  cases. `7e5ef99`

---

## 2026-08-02 — LLM feature write-up

### Documentation

- **`LLM_FEATURE.md`** — the prompt design for the diagnosis endpoint, its implementation,
  the fallback behaviour when no key is configured, and sample output. Later moved to
  [design/LLM_FEATURE.md](../design/LLM_FEATURE.md). `7b72190`

---

## 2026-08-01 — Client validation and cascade delete

### Added

- **`ValidationException` → HTTP `400`.** Creating a client with a `managerId` belonging
  to a member who is not a `CLIENT_MANAGER` is now rejected with
  `{"error": "ValidationError", "detail": …}` instead of being accepted. The new exception
  and its handler in `app/main.py` give the codebase a general route from a broken
  business rule to a `400`. `173d454`

### Changed

- **Deleting an instance now cascades to its alerts through the ORM relationship** rather
  than a manual delete in the service. `2707e70`

---

## 2026-07-31 — Monitoring module completed

### Changed

- **`PATCH /api/instances/{id}/status` is idempotent.** A repeated request carrying the
  same status and CPU usage returns without touching the row. This matters because the
  monitoring module uses `updatedAt` as the best available "status changed at" value for
  the 48-hour STOPPED rule — re-sending the same request must not restart that
  clock. `8e24ae1`
- **The three `/api/monitor/*` checks return instances ordered by `id`**, so results are
  deterministic rather than dependent on the database's row order. `8e24ae1`
- **`LONG_STOPPED` hours are computed from a single `now`** captured before the loop
  instead of re-reading the clock per instance. `8e24ae1`

### Added

- **`tests/conftest.py` and `tests/test_member_c.py`** — the first tests in the project,
  covering the monitoring endpoints against an in-memory database. `8e24ae1`
- **`docs/MEMBER_C.md`** — the instance-status and monitoring assignment scope; later
  moved to [team/MEMBER_C.md](../team/MEMBER_C.md). `8e24ae1`

---

## 2026-07-11 — Initial codebase

### Added

- **The whole API in one commit** — 30 files, ~1,800 lines. `d3519a4`
  - **MVC layout under `app/`** — `models/`, `schemas/`, `controllers/`, `services/` and
    `core/`, plus `main.py`, `config.py`, `database.py` and `seed.py`.
  - **19 endpoints plus a health check**, across auth, instances, monitoring, alerts and
    clients.
  - **Five tables** — members, clients, instances, alerts, cost snapshots.
  - **JWT authentication** with role scoping (`ADMIN`, `CLIENT_MANAGER`) in `app/core/`.
  - **Domain exceptions** — `NotFoundException`, `ForbiddenException` and
    `ActiveInstanceException` — mapped to `404`, `403` and `409` by handlers in
    `app/main.py`.
  - **The LLM diagnosis service**, with a deterministic fallback when no API key is
    configured.
  - **Idempotent demo seeding** on startup, and `docs/ERD.md`.
- **`LICENSE`** — MIT. `0485d7b`

---

## Contributors

| Contributor | Scope |
|---|---|
| Thái Văn Lâm | Initial codebase, LLM feature and fix, Swagger capture tooling, test suite, documentation set |
| gimmethejeremie | Monitoring module completion (2026-07-31) |
| Dinh Thanh | Client `managerId` validation, ORM cascade delete (2026-08-01) |
| hanbanthan | Import cleanup (2026-08-10) |

---

## Adding an entry

This document follows the same rule as every other: it changes in the **same commit** as
the change it records.

1. Write the entry under a heading for the date the change lands, newest first. Reuse the
   day's heading if one already exists; name a new one after what that day's work
   accomplishes.
2. File it under **Added**, **Changed**, **Fixed**, **Removed** or **Documentation**.
3. Say what a reader would *notice* — a status code that changed, an endpoint that
   appeared, a number that moved — and why. A diff summary is not an entry; the commit
   hash already leads to the diff.
4. Cite the commit hash at the end of the bullet.
5. Add a row to [At a glance](#at-a-glance) whenever a new date heading is created.

Scratch and merge commits are not recorded here. Several `test.md` / `test.txt` commits
sit in the history from branch experiments in July 2026; they changed nothing in `app/`
and were removed in `13aabcd`.

---

## Related

| Document | Why |
|---|---|
| [../contributing/COMMITS.md](../contributing/COMMITS.md) | The commit prefixes and scoping this document mirrors |
| [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md) | Which other document a change updates alongside this one |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | The steps and numbers a behaviour change may invalidate |
| [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) | Findings recorded on 2026-08-29, none yet fixed |
| [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) | What the 104 tests pin down |
| [../README.md](../README.md) | Documentation index |
