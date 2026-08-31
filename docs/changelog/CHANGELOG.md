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
throughout. No fix has been applied yet; the findings are recorded, not resolved.

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
