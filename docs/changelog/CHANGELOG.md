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
| [2026-09-01](#2026-09-01--requirements-test-cases-and-a-user-manual) | Requirements, test cases and a user manual | BRD, SRS, FRS, use cases and user stories; a test case specification; an end-user manual |
| [2026-09-01](#2026-09-01--security-review) | Security review | 15 reproduced findings, two critical — a signing key anyone can read, and credentials served to anyone |
| [2026-09-01](#2026-09-01--perf-09-fixed-the-alert-listing-joins-only-when-it-has-to) | PERF-09 fixed | An `ADMIN` reading alert history no longer joins `instances` for a column nothing uses |
| [2026-09-01](#2026-09-01--perf-07-fixed-every-list-endpoint-is-paginated) | PERF-07 fixed | Every list endpoint paginates — **breaking**; a response no longer grows with the table |
| [2026-09-01](#2026-09-01--perf-06-fixed-a-commit-no-longer-re-selects-the-rows-it-returns) | PERF-06 fixed | A monitoring scan is four statements whether it returns 4 rows or 500 |
| [2026-09-01](#2026-09-01--operations-runbooks) | Operations runbooks | Deployment, configuration and 15 incident runbooks for whoever is on call |
| [2026-09-01](#2026-09-01--perf-05-fixed-a-scan-dedups-in-one-query-and-writes-in-one-insert) | PERF-05 fixed | A monitoring scan costs three statements instead of two per instance |
| [2026-09-01](#2026-09-01--perf-04-fixed-the-filtered-and-sorted-columns-are-indexed) | PERF-04 fixed | Every list endpoint seeks its rows instead of scanning the table |
| [2026-09-01](#2026-09-01--perf-03-fixed-the-llm-call-is-bounded-and-holds-no-connection) | PERF-03 fixed | A diagnosis waits at most 60 s, and holds no database connection while it waits |
| [2026-09-01](#2026-09-01--docs-sync-check) | Docs-sync check | The documentation rule is reminded at commit time, not only written down |
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

## 2026-09-01 — Requirements, test cases and a user manual

### Documentation

- **Added [requirements/](../requirements/README.md)** — the specification layer the
  repository did not have. [BRD.md](../requirements/BRD.md) records the business context
  (the spreadsheet these ten client companies were tracked in), six objectives,
  stakeholders, scope, and 19 business requirements. [SRS.md](../requirements/SRS.md)
  carries ten functional requirements and the non-functional set — performance, security,
  reliability, maintainability, portability, usability — each marked with how it is
  verified. [FRS.md](../requirements/FRS.md) specifies 24 functions, inputs through
  failure paths, including the three cross-cutting ones (pagination, scoping, error
  mapping) that every endpoint inherits.
  [USE_CASES.md](../requirements/USE_CASES.md) holds 15 use cases with their alternative
  flows and 30 user stories with Given/When/Then criteria naming the test that holds each
  one. `4f492fb`
- **Added [testing/TEST_CASES.md](../testing/TEST_CASES.md)** — 100 cases with
  precondition, steps, data and exact expected result, each linked to the automated test
  that runs it. The cases that **cannot** be automated say so: the December forecast
  roll-over, the diagnosis timeout, and mid-month SLA windows are marked *Manual* rather
  than left looking covered. It sits beside
  [FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md), which describes how the suite is
  built rather than what must be checked. `1bcd427`
- **Added [manual/USER_MANUAL.md](../manual/USER_MANUAL.md)** — the end-user document, in
  task order rather than endpoint order, with an error-message table mapping every status
  code to what to do about it, and an FAQ answering the questions the design provokes:
  why a repeated status update changes nothing, why a resolved alert comes back, and why
  an SLA figure must not be quoted to a client. `ec11e69`
- **Wired the new folders into the indexes** — [../README.md](../README.md), the root
  [README.md](../../README.md) and the folder READMEs, per rule 4 of
  [contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md). The root README's
  "eleven documentation folders" was already stale at thirteen; it now reads fifteen.
  `47d9ebc`
- **Extended the source → document mapping** in
  [contributing/DOCUMENTATION.md § 5](../contributing/DOCUMENTATION.md#5-source--document-mapping)
  and in `MAPPING` in [check_docs_sync.py](../../scripts/check_docs_sync.py), in the same
  commit as the rule requires: a change under `app/controllers/` now also points at the
  FRS and the user manual, `app/schemas/` at the FRS, and `tests/` at the test cases. The
  check only warns when *none* of a row's documents are staged, so the added rows raise no
  new noise. `490b7db`

Traceability now runs end to end — **BR → FR/NFR → F-\* → UC/US → TC** — and it is
traceability against the delivered system: the documents were written from the code and
the tests, so where a requirement is only partly met they say so. BR-13 (SLA reporting) is
recorded as partially met against the uptime approximation, and NFR-SEC-06 and NFR-SEC-07
are recorded as **not met** against the open findings in
[security/SECURITY_BUGS.md](../security/SECURITY_BUGS.md).

No code changed and no behaviour moved. All 124 tests still pass.

---

## 2026-09-01 — Security review

### Documentation

- **Added [security/SECURITY_BUGS.md](../security/SECURITY_BUGS.md)** — 15 findings on
  injection, information disclosure and session integrity, each **reproduced** against the
  seeded API through the same `TestClient` harness the suite uses, with the application
  code unmodified. Two are rated critical, and both bypass authentication without touching
  the API's logic: the default `SECRET_KEY` is a literal in `config.py` and `.env.example`,
  and a token forged with it was accepted at an `ADMIN`-only endpoint (SEC-01); the three
  seeded accounts and their passwords are served to anyone by `/openapi.json` and `/docs`
  (SEC-02). The session finding the review was asked for is SEC-04 — there is no logout and
  no revocation, so an issued token cannot be stopped before its expiry — blocked behind
  SEC-08, because the token carries no `jti` or `iat` to name in a denylist. The document
  also records what was checked and found sound: **SQL injection is not present and is
  structurally prevented**, and no stack trace reaches a client. `97955e9`
- **Indexed the new folder** from [../README.md](../README.md), the root
  [README.md](../../README.md), [../performance/README.md](../performance/README.md) and
  this folder's README. `97955e9`

No code changed and nothing is fixed — this is the register, in the same shape as
[performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md), and the order to
work through it is at
[Where to start](../security/SECURITY_BUGS.md#where-to-start). All 124 tests still pass,
which is the point: none of them catch any of this.

---

## 2026-09-01 — PERF-09 fixed: the alert listing joins only when it has to

The first of the two remaining medium findings closed, and the smallest fix in this
series: two lines moved inside a branch. No behaviour changed. 124 tests pass — the 123
that existed, unchanged, plus one new one.

### Fixed

- **`list_alerts` joins `instances` only when a scope has to be applied.**
  [../../app/services/alert_service.py](../../app/services/alert_service.py) joined
  unconditionally, but the join exists solely to reach `Instance.clientId` for a
  `CLIENT_MANAGER`'s scope filter. An `ADMIN` has `client_ids is None`, never applies that
  filter, and was paying an index lookup into `instances` for every row scanned — twice per
  request since [PERF-07](../performance/PERFORMANCE_BUGS.md#perf-07) added the count query
  over the same statement. Both `ADMIN` plans lose their per-row
  `SEARCH instances USING COVERING INDEX ix_instances_id`; the count's plan collapses to a
  single `SCAN alerts USING COVERING INDEX ix_alerts_id`. The `CLIENT_MANAGER` query is
  byte for byte what it was.
- **Measured as a time, not a count**, because the statement count does not change — 3 for
  an `ADMIN`, 4 for a `CLIENT_MANAGER`, before and after. Median of 60 `ADMIN`
  `GET /api/alerts` requests: unchanged at 4.0 ms on the seed's 9 alerts, and **5.7 ms →
  4.5 ms** with the table grown to 20,009. The join costs what `alerts` costs, and `alerts`
  is the table nothing prunes. At seed scale the difference is inside the noise, which the
  finding says rather than rounding in its own favour.

### Added

- **`test_deleting_an_instance_removes_its_alerts_from_the_history`** in
  [../../tests/test_alerts.py](../../tests/test_alerts.py). An inner join filters as well
  as costs, so removing one is only safe if no alert can outlive its instance — otherwise
  an orphaned row would now be listed to an `ADMIN` while still hidden from a
  `CLIENT_MANAGER`. `Instance.alerts` is declared `cascade="all, delete-orphan"`, so none
  can. The test deletes instance 3 after a scan and asserts its `LONG_STOPPED` alert goes
  with it and the history falls from 9 to 8, because losing that cascade would now be a
  visible bug rather than only a storage one.

### Documentation

- [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) — PERF-09 marked
  **Fixed**, with what landed, the safety argument for dropping an inner join, the
  before/after plans and latencies, and what is deliberately left alone on the
  `CLIENT_MANAGER` path. Two corrections in place: the finding's quoted plan still carried
  a `USE TEMP B-TREE FOR ORDER BY` that
  [PERF-04](../performance/PERFORMANCE_BUGS.md#perf-04) and PERF-07 had already removed, so
  the join was the whole of the remaining waste; and the measurement section said the seed
  holds 16 instances where it has always held 15
  ([../demo/SEED_DATA.md](../demo/SEED_DATA.md)). Step 8 of the suggested order splits into
  8a (done) and 8b, since the conditional join carries none of the risk that the auth-path
  changes do.
- [../business-rules/ALERTING.md](../business-rules/ALERTING.md) — § 5 now says why the
  delete cascade is load-bearing for the listing rather than merely tidy.
- [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md),
  [../onboarding/READING_ORDER.md](../onboarding/READING_ORDER.md),
  [../performance/README.md](../performance/README.md) and the test counts in
  [../../README.md](../../README.md) and [../../CLAUDE.md](../../CLAUDE.md) — the new case,
  the moved `resolve_alert` line reference, 9 of 15 findings fixed, 123 → 124.

---

## 2026-09-01 — PERF-07 fixed: every list endpoint is paginated

The last high-severity performance finding closed, and the first change in this project
that **breaks the API contract**. Six endpoints that returned a JSON array now return the
`PageResponse` envelope `GET /api/instances` has always used. 123 tests pass — 104 as
before, 14 of them updated for the new shape, plus 19 new ones.

### Changed — breaking

- **`GET /api/alerts`, `GET /api/clients`, `GET /api/clients/{id}/instances`,
  `GET /api/monitor/warnings`, `/errors` and `/long-stopped` return
  `PageResponse[T]`**, not `T[]`. A client that iterated the response now reads `.items`.
  All six take `page` (default `1`) and `size` (default `10`, max `100`) and answer `422`
  outside those bounds. `total` is the count after filters and role scoping, so a
  `CLIENT_MANAGER` is never told how many rows exist outside their scope. Measured on the
  demo data grown with 700 extra instances, `GET /api/alerts` went from 709 rows and
  144,036 bytes to 10 rows and 2,108 bytes, and its peak allocation per request from
  2,220 KiB to **96 KiB** — where at 3,000 extra instances the old shape reached 9,024 KiB
  and the new one is still 97 KiB. `alerts` is the table nothing prunes, which is why it
  needed the bound first.
- **`GET /api/monitor/report` caps `unresolvedAlerts` at the 20 most recent**, and
  `unresolvedAlertCount` is now a `func.count()` rather than the length of that array. The
  two fields no longer answer the same question: the count is the true total and can
  exceed the preview beside it, with the full history behind the paginated
  `GET /api/alerts`. Before this the report built the entire unresolved list purely to
  take its length.
- **Detection is unchanged; only its response is paged.** The three monitoring scans still
  record an alert for **every** instance meeting their condition, not only those on the
  page returned — `?size=1` against four high-CPU instances answers with one and records
  four. Paginating the recording would have made detection depend on how far a dashboard
  scrolled, which is the one way this change could have become a functional regression.
  Stated in [../business-rules/ALERTING.md § 2](../business-rules/ALERTING.md#2-detection-writes-alerts)
  and pinned by a test.
- **`id` is now the final sort key on `GET /api/alerts` and `GET /api/instances`.** Rows
  tied on the sort key have no defined order between them, so a row could be served on two
  pages or on none as a caller walked them — and on `/api/alerts` ties are the normal case,
  because a scan stamps every alert it records with the same instant. The plans are
  unchanged: SQLite already holds a non-unique index in `(key, rowid)` order, so the
  ordered index scan [PERF-04](../performance/PERFORMANCE_BUGS.md#perf-04) bought is not
  given back.

### Added

- **[app/pagination.py](../../app/pagination.py)** — the `page`/`size` bounds as reusable
  `Annotated` aliases, and `paginate()`, which returns `(items, total, totalPages)` for a
  query. One definition, seven endpoints: `size` cannot be capped at `100` on one route and
  something else on the next. `GET /api/instances` was rewired through it rather than
  keeping its own copy.
- **19 functional tests.** The ones worth naming pin behaviour a reader would otherwise
  have to trust: `a_scan_records_alerts_for_every_match_not_only_the_page`,
  `monitoring_scans_are_unchanged_by_the_batch_size` (identical results at
  `ID_BATCH_SIZE` 1, 3 and 500), `alert_pages_partition_the_history_without_gaps_or_repeats`
  and `pages_partition_a_non_unique_sort_without_gaps_or_repeats` for the tiebreaker,
  `report_caps_the_embedded_alerts_but_not_the_count`, and
  `cost_and_sla_still_cover_every_instance_not_a_page`.

### Fixed

- **[PERF-07](../performance/PERFORMANCE_BUGS.md#perf-07)**, as above.
- **[PERF-08](../performance/PERFORMANCE_BUGS.md#perf-08) — the count query no longer
  sorts in order to count.** Not a separate change: the shared `paginate()` helper had to
  count correctly before six more endpoints started calling it, so writing the old
  `query.count()` into it would have spread the defect rather than fixed it. The statement
  went from a co-routine subquery selecting all ten columns with the `ORDER BY` intact, to
  `SELECT count(instances.id) FROM instances WHERE ...`; the plan went from four steps
  including a `USE TEMP B-TREE FOR ORDER BY` to a single **covering** index seek.
- **A monitoring scan no longer materialises its whole result set.** `_scan` walks the
  matches in id-keyset batches of `ID_BATCH_SIZE`, recording as it goes and keeping only
  the requested window, so `total` and the page fall out of a walk the scan was making
  anyway — no extra count query — and memory is bounded by one batch. The cost, stated
  plainly: at 704 matching instances a scan issues 7 statements against 5, two more per
  500 instances, in exchange for a response and a working set that stop growing.

### Documentation

- [../api/CONVENTIONS.md](../api/CONVENTIONS.md) — § 1 rewritten: pagination now lists all
  seven endpoints rather than declaring `GET /api/instances` the only one, with the report
  named as the deliberate exception, the detection-is-not-paginated rule, and § 3 gaining
  why `id` closes every sort.
- [../api/ENDPOINTS.md](../api/ENDPOINTS.md), [../api/OVERVIEW.md](../api/OVERVIEW.md),
  [../api/ERRORS.md](../api/ERRORS.md) — the six response shapes, the new query parameters
  and the `422`s they can now return.
- [../business-rules/ALERTING.md](../business-rules/ALERTING.md) — § 2 gains the asymmetry
  between what a scan detects and what it returns; § 5 and § 6 the paged history and the
  capped report preview. [COST.md](../business-rules/COST.md) and
  [SLA.md](../business-rules/SLA.md) say why their per-instance arrays are *not* paged.
- [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) — `pagination.py` in the layout,
  and why it sits outside the layer table on purpose.
- [../onboarding/READING_ORDER.md](../onboarding/READING_ORDER.md) — a new § 2.3 for
  `pagination.py`, stops added for `_scan`, `_client_instances_query` and
  `list_client_instances`, and all 82 stops renumbered.
- [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) — PERF-07 and
  PERF-08 marked **Fixed**, with the measured response sizes, the peak-allocation table at
  three database sizes, the statement counts, the plans, and an explicit list of what the
  fix does *not* address: the breaking change itself, the join PERF-09 still carries — now
  paid twice per request — the two unbounded arrays in the cost and SLA responses, and
  deep `OFFSET` paging.
- [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) — steps 5, 12, 15 and 16 show the
  envelope, and step 12 gains the `?size=1` demonstration that a paged scan still records
  every alert.
- [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md),
  [../team/MEMBER_C.md](../team/MEMBER_C.md), and the test count in every document quoting
  it: 104 → 123.
- [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md) and
  [../../scripts/check_docs_sync.py](../../scripts/check_docs_sync.py) — a mapping row for
  `app/pagination.py`, added to both copies as that rule requires.

---

## 2026-09-01 — PERF-06 fixed: a commit no longer re-`SELECT`s the rows it returns

The third high-severity performance finding closed, and the last one that made a
statement count grow with a response. No behaviour changed and all 104 tests pass
unchanged.

### Fixed

- **`SessionLocal` sets `expire_on_commit=False`.** On SQLAlchemy's default a `commit()`
  marks every object the session has loaded expired, so the next read of any attribute
  re-fetches its row. The monitoring endpoints commit the alerts they recorded and then
  return the instances they scanned, so serialising the response issued one `SELECT` per
  row — a wasted round trip for each instance in the answer.
  [../../app/database.py](../../app/database.py) now builds the factory with the expiry
  off. Measured on the seeded demo data, an `ADMIN` `GET /api/monitor/warnings` first scan
  fell from **8 statements to 4**, `/errors` from 6 to 4 and `/long-stopped` from 7 to 4;
  as a `CLIENT_MANAGER` all three fell from 7 to 5. With
  [PERF-05](../performance/PERFORMANCE_BUGS.md#perf-05) this makes a scan a fixed four
  statements at any result size — 500 matching instances would cost what four do, against
  1,502 before the two fixes.
- **Nothing relied on the expiry.** The four functions that want state back after their
  commit — `create_instance`, `update_status`, `create_client` and `resolve_alert` — call
  `db.refresh()` explicitly on the following line, and each was measured to issue exactly
  the statements it did before: `POST /api/instances` 4, `PATCH /api/instances/{id}/status`
  5, `PATCH /api/alerts/{id}/resolve` 6, `POST /api/clients` 4. `GET /api/monitor/report`
  never commits, so it never had anything to expire, and is unchanged at 5.
- **The test fixture got the same argument.** `tests/conftest.py` builds its own session
  factory, so without it the suite would have gone on exercising SQLAlchemy's defaults
  rather than the session the API runs on. The tests that read the session directly after
  a request — the post-delete `db.get(Instance, 1) is None`, the `updatedAt` comparison
  across an idempotent update — pass unchanged, which is what a change to expiry semantics
  would break first.

### Documentation

- [../design/DATABASE.md](../design/DATABASE.md) — a new § 3 *The session factory*: what
  each `sessionmaker` argument does, why SQLAlchemy's expiry default is the wrong one for
  a per-request session, the measured cost it carried, and what `db.refresh()` still does.
  Sections 3–7 renumbered to 4–8; the § 2 link from
  [../operations/RUNBOOKS.md](../operations/RUNBOOKS.md) is unaffected.
- [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) — § 5 gains *The session factory*
  beside the pool and pragma subsections.
- [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) — PERF-06 marked
  **Fixed**, with what landed, the before/after counts for all three endpoints as both
  roles, and the unchanged-endpoint table. The finding's claim that the waste happened
  "even when nothing was written" is corrected in place: that measurement predates
  [PERF-01](../performance/PERFORMANCE_BUGS.md#perf-01), and since a repeat poll stopped
  committing it has had no expiry to pay for — re-measured, a repeat poll costs the same
  with and without this fix. The measurement method records how the "before" column was
  produced.
- [../performance/README.md](../performance/README.md) — the fixed count, a PERF-06 bullet,
  and DATABASE.md added to the related table.
- [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) — § 2 lists the session
  factory among the details that make the fixture work.
- [../onboarding/READING_ORDER.md](../onboarding/READING_ORDER.md) — stop 8 notes the
  setting; stops 9, 10, 77 and the `get_db` seam note carry the line numbers the change
  moved.

---

## 2026-09-01 — Operations runbooks

The documentation covered how the system is built and how it behaves, but not how to run
it — the tenth folder answers that. No code behaviour changed.

### Documentation

- **[../operations/](../operations/README.md)** — a new folder for running the API:
  [DEPLOYMENT.md](../operations/DEPLOYMENT.md) (local, single-server and Vercel launches,
  what a healthy start logs, the four calls that verify a deployment, upgrade, rollback,
  backup and reset), [CONFIGURATION.md](../operations/CONFIGURATION.md) (every setting and
  its precedence, generating `SECRET_KEY`, the Anthropic key and its fallback, what
  `DATABASE_URL` selects, reading back the effective configuration with secrets redacted)
  and [RUNBOOKS.md](../operations/RUNBOOKS.md) (fifteen incident runbooks — symptom, cause,
  fix, verification — with a 60-second triage, a guide to the log lines, and what to
  collect before escalating).
- Every error message, command and expected output in the three documents was reproduced
  against this repository rather than recalled — the startup and bind-failure logs, the
  `unable to open database file` and missing-driver failures, the LLM fallback warning
  line, the index listing, the `PRAGMA journal_mode`/`integrity_check` probes, the
  `VACUUM INTO` backup, and the four verification calls against a running server.
- Two operational consequences that were implicit are now stated where an operator will
  look for them: the default `SECRET_KEY` is published in this repository and must be
  replaced before a deployment is reachable, and a serverless deployment cannot keep its
  database — every cold start re-seeds
  ([../performance/PERFORMANCE_BUGS.md § PERF-15](../performance/PERFORMANCE_BUGS.md#perf-15)).

### Changed

- **The docs-sync check maps two more sources.** `app/config.py` now also asks for
  [../operations/CONFIGURATION.md](../operations/CONFIGURATION.md) and `app/main.py` for
  [../operations/DEPLOYMENT.md](../operations/DEPLOYMENT.md), in both copies of the
  mapping — section 5 of [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md)
  and `MAPPING` in [../../scripts/check_docs_sync.py](../../scripts/check_docs_sync.py) —
  so a new setting or a change to the startup hook reminds its operator document too.

---

## 2026-09-01 — PERF-05 fixed: a scan dedups in one query and writes in one insert

The second high-severity performance finding closed. The alerting rule is unchanged — same
guard, same alerts, same ordering — and all 104 tests pass unchanged.

### Fixed

- **Alert deduplication no longer runs one query per instance.** Each monitoring scan
  called `_has_unresolved_alert` inside its loop, so a scan cost one `SELECT` per matching
  instance plus one `INSERT` per alert — the statement count grew with the result set, on
  the three endpoints a dashboard polls most often.
  [../../app/services/monitor_service.py](../../app/services/monitor_service.py) now reads
  back which of the scanned instances already carry an unresolved alert of that type in a
  single query, and inserts the alerts for the rest as one batch. Measured on the seeded
  demo data, an `ADMIN` `GET /api/monitor/warnings` fell from **14 statements to 8** on the
  first scan and from **6 to 3** on the repeat poll — and the two groups that scaled with
  the result set are now one statement each, so 500 matching instances would cost the same
  three statements as four do.
- **The batch insert is a Core `insert()`, not `add_all`.** The ORM has to read back the
  generated `id` of every row it writes, and SQLite's `RETURNING` gives no order guarantee
  to correlate them by, so `add_all` still emitted one `INSERT` per alert — measured, not
  assumed. A scan never uses the alert rows it writes, so the ids are not needed and the
  whole batch goes out as a single `executemany`. `isResolved` and `detectedAt` still come
  from the model's column defaults.
- **The dedup probe's `IN` list is chunked** at `ID_BATCH_SIZE = 500`. SQLite rejects a
  statement with more than 32,766 bind parameters, and these endpoints put no upper bound
  on how many instances they return ([PERF-07](../performance/PERFORMANCE_BUGS.md#perf-07)),
  so an unchunked list would have traded an N+1 for an outright failure on a large enough
  deployment. Driving the scans with the batch size forced to 1, 2 and 3 produces the same
  instances, alert counts and dedup outcome as the default.

### Documentation

- [../business-rules/ALERTING.md](../business-rules/ALERTING.md) — § 3 *Duplicate
  prevention* describes the check as one query for the scan rather than a call per
  instance, and states that the rule it enforces is unchanged.
- [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) — PERF-05 marked
  **Fixed**, with what landed, the before/after statement counts for all three endpoints as
  both roles, and the after-trace; the PERF-01, PERF-04 and PERF-06 cross-references that
  called the dedup probe per-instance corrected; the measurement method now records how the
  "before" column was produced and how the chunking was checked.
- [../performance/README.md](../performance/README.md) — the fixed count and a PERF-05
  bullet.
- [../onboarding/READING_ORDER.md](../onboarding/READING_ORDER.md) — stop 43 is
  `_instances_with_unresolved_alert` and stop 44 `_record_alerts`, with the line numbers
  the change moved.

---

## 2026-09-01 — PERF-04 fixed: the filtered and sorted columns are indexed

The first of the high-severity performance findings closed. No API contract changed — same
routes, same schemas, same status codes — and all 104 tests pass unchanged.

### Fixed

- **The columns the API filters and sorts on are now indexed.** `index=True` appeared only
  on primary keys and `members.email`, and SQLite creates no index for a foreign key on its
  own, so every list endpoint was a full table scan: `SCAN instances` for the main list,
  `SCAN clients` for the accessible-client lookup every `CLIENT_MANAGER` request makes, and
  `SCAN alerts` for the dedup probe each monitoring scan runs *once per instance*.
  [../../app/models/models.py](../../app/models/models.py) declares five indexes —
  `clients.managerId`, `instances.(clientId, status)`, `instances.region`,
  `instances.updatedAt`, and the composite `alerts.(instanceId, alertType, isResolved)`
  with `alerts.detectedAt` beside it. Measured on the same seeded data, every one of those
  scans became a `SEARCH … USING INDEX`, and the two `USE TEMP B-TREE FOR ORDER BY` steps —
  the alert listing's `detectedAt` sort and `?sort=-updatedAt` — disappeared.
  A sixth index, on `alerts.isResolved`, was proposed by the finding and **not** added:
  measured, it makes `GET /api/alerts?isResolved=false` slower, because nearly every row is
  `false`, so SQLite takes the index, matches almost the whole table, and then has to sort
  what it matched instead of reading it in order off `ix_alerts_detectedAt`.
- **Startup creates any index the database file is missing.** `Base.metadata.create_all`
  skips a table that already exists and its indexes with it, so a declared index would never
  reach a `monitoring.db` created before the declaration — and the project has no migration
  step. `lifespan` ([../../app/main.py](../../app/main.py)) now follows `create_all` with one
  `index.create(bind=engine, checkfirst=True)` per index in the metadata. It is idempotent,
  issues no `CREATE` on a file that already has them all, and means this change needs no
  database rebuild. Indexes are the one schema change that reaches an existing file this
  way; a column change still means deleting `monitoring.db`.

Still open on the same code paths: the dedup probe is a seek now but there is still one of
them per instance ([../performance/PERFORMANCE_BUGS.md#perf-05](../performance/PERFORMANCE_BUGS.md#perf-05)),
the pagination count still sorts in order to count
([PERF-08](../performance/PERFORMANCE_BUGS.md#perf-08)), and two `ADMIN`-path scans stay
scans — `check_warnings` filters on the unindexed `cpuUsage`, and `check_long_stopped`'s
range on `updatedAt` is one SQLite still prefers to scan.

### Documentation

- [../design/ERD.md](../design/ERD.md) — new § *Indexes*: what is indexed, what each index
  serves, and why `alerts.isResolved` and `cost_snapshots.clientId` are deliberately left
  out. The *No migrations* known gap now records the index exception.
- [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) — § 5 *Startup* is a three-step
  list; step 2 is the index pass and why `create_all` alone is not enough.
- [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) — PERF-04 marked
  **Fixed**, with what landed, the before/after plan table, the rejected sixth index and
  what the indexes do not fix; the PERF-05 and PERF-10 cross-references that called these
  queries full scans corrected; the measurement method now records how both columns of the
  plan table were produced — including that dropping indexes from a live connection leaves
  the plans unchanged, so the "before" column needs its own engine.
- [../performance/README.md](../performance/README.md),
  [../onboarding/READING_ORDER.md](../onboarding/READING_ORDER.md) — the fixed count, and
  the `main.py` and `models.py` line numbers the change moved.

---

## 2026-09-01 — PERF-03 fixed: the LLM call is bounded and holds no connection

The third and last critical performance finding closed. No API contract changed — same
route, same schema, same status codes — and all 104 tests pass unchanged.

### Fixed

- **The Anthropic client now has a timeout and a retry cap.**
  `anthropic.Anthropic(...)` was constructed with neither, so the SDK's defaults applied:
  a 600-second read timeout across 3 attempts, roughly **30 minutes** for one diagnosis,
  with the request holding a threadpool worker throughout.
  [../../app/services/llm_service.py](../../app/services/llm_service.py) now sets
  `TIMEOUT_SECONDS = 30.0` and `MAX_RETRIES = 1` on both construction branches — the one
  that hands over the key from `.env` and the one that lets the SDK resolve credentials
  itself — for a **60-second** worst case. A diagnosis that exceeds it raises
  `APITimeoutError`, which the existing `except Exception` already treats like any other
  provider failure: the caller still gets `200` with `source: "rule-based"`. The numbers
  are a product choice, not a tuning one — an answer that arrives half an hour after an
  incident is worth less than the instant deterministic one.
- **The database connection goes back to the pool before the provider call.** `get_db`
  keeps a session, and therefore a pooled connection, checked out for the whole request,
  and this is the one handler that spends most of its time on the network with no query
  left to run. `diagnose_instance` loads the instance, runs the access check, loads the 10
  most recent alerts, and then calls `db.close()` before `llm_service.diagnose(...)`
  ([../../app/controllers/instance_controller.py](../../app/controllers/instance_controller.py)).
  `Session.close()` resets the session rather than tearing it down, so the `get_db` close
  after the response is a no-op, and it detaches the loaded rows **without** expiring them,
  so the prompt and the response body keep reading their values from memory. Measured with
  20 concurrent diagnoses all inside the provider call at once: **20** connections held
  before, **0** after.

The invariant this introduces: every field the prompt or the response needs must be loaded
before `db.close()`, relationships included — a field added after that line would raise
`DetachedInstanceError`. It is written down in
[../design/LLM_FEATURE.md § 4.5](../design/LLM_FEATURE.md#45-request-limits-and-the-database-connection).

Still open: the request occupies a threadpool worker for the length of the call — bounded
at 60 seconds now, but held. Freeing that means `AsyncAnthropic` with an `async def`
endpoint, recorded as future work. The client is also still built per request
([PERF-14](../performance/PERFORMANCE_BUGS.md#perf-14)).

### Documentation

- [../design/LLM_FEATURE.md](../design/LLM_FEATURE.md) — new § 4.5 *Request limits and the
  database connection*; the flow diagram, Path A pseudocode, the failure-trigger table, the
  authentication section and the *Synchronous call* limitation updated to match. The
  `max_tokens` row of § 3.4 was corrected in passing: it documented `1024`, while the code
  has sent `16000` since adaptive thinking was enabled — thinking tokens come out of the
  same budget.
- [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) — PERF-03 marked
  **Fixed**, with what landed, what it does not, and the before/after tables; the
  connection-hold method added to § How these were measured, and the caveat that PERF-03
  was derived rather than observed narrowed to the 30-minute figure alone.
- [../performance/README.md](../performance/README.md),
  [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md),
  [../api/ENDPOINTS.md](../api/ENDPOINTS.md), [WALKTHROUGH.md](../demo/WALKTHROUGH.md) and
  [../onboarding/READING_ORDER.md](../onboarding/READING_ORDER.md) updated to match.

---

## 2026-09-01 — Docs-sync check

One commit turning rule 3 into a commit-time reminder. No application source changed.

### Added

- **[../../scripts/check_docs_sync.py](../../scripts/check_docs_sync.py)** — reads the
  staged paths, applies the § 5 source → document mapping, and names the documents that
  were not staged beside the code. It **warns and lets the commit through**: the rule
  asks for a document when *behaviour* changes, and no script can tell a behaviour change
  from a rename, so it reports candidates and leaves the judgement to the author. Beyond
  the mapping it reminds about the four conditional documents — the Swagger captures for
  a source that can alter a response, [CHANGELOG.md](CHANGELOG.md) and
  [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) for any `app/` change, and
  [../onboarding/READING_ORDER.md](../onboarding/READING_ORDER.md) only when the staged
  diff actually adds or removes a `def` or a `class`, since that document cites line
  numbers. Staging any one of a source's mapped documents silences it for that source.
- **[../../scripts/hooks/pre-commit](../../scripts/hooks/pre-commit)** — runs the script
  for every contributor. Installed once per clone with
  `git config core.hooksPath scripts/hooks`; the repository had no hook directory before
  this, only git's `.sample` files. A first `.gitattributes` pins `scripts/hooks/*` to LF
  endings — this clone has `core.autocrlf=true`, and a CRLF shebang line stops `sh` from
  running the hook at all on macOS and Linux.
- **A `PreToolUse` hook in [../../.claude/settings.json](../../.claude/settings.json)** —
  runs the same script with `--hook` before any `git commit` an agent issues, and answers
  with the warning as `systemMessage` and `additionalContext`. The settings file is
  checked in, so this side needs no per-clone setup. The existing `WebFetch` permissions
  are untouched.

### Documentation

- **Added rule 7, *The check that reminds you*, to
  [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md#7-the-check-that-reminds-you)**
  — what the check does, why it warns instead of blocking, the two entry points and their
  setup, and the requirement that a new mapping row lands in both the § 5 table and the
  script's `MAPPING`. *Writing style* and *Related* renumbered to 8 and 9; the § 5 and § 6
  anchors cited elsewhere are unchanged.
- **Recorded it in the summaries that describe the rule set** — the *short version* and
  *Related* table in [../contributing/README.md](../contributing/README.md),
  *Conventions for these documents* in [../README.md](../README.md), and *Contributing*
  plus the `scripts/` line of the project tree in the root
  [README.md](../../README.md).
- **Condensed it into [../../CLAUDE.md](../../CLAUDE.md)** next to the mapping, so an
  agent knows both that the mapping has a second copy to keep in step and that the hook's
  warning is a reminder to act on.

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
| [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) | Findings recorded on 2026-08-29; eight fixed since |
| [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) | What the tests pin down |
| [../README.md](../README.md) | Documentation index |
