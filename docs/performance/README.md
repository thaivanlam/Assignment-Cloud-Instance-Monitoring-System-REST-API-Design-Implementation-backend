# Performance

Findings on latency, throughput, and concurrency in `app/` — what is slow, why, and what
it would take to fix.

| Document | Contents |
|---|---|
| [PERFORMANCE_BUGS.md](PERFORMANCE_BUGS.md) | 15 measured findings ranked by severity, each with cause, evidence, and fix; a **Status** column saying which are fixed; a suggested order of work; the measurement method |

## The short version

Everything in `PERFORMANCE_BUGS.md` is a performance defect, not a functional one — the
104 tests pass and the API returns correct answers throughout. Three findings are rated
critical, and all three are now fixed, as are the first three of the high-severity ones:

- **PERF-01** — *fixed.* The three `/api/monitor/*` endpoints are `GET`s that wrote and
  committed unconditionally, and SQLite ran with a rollback journal, so every dashboard
  poll took an exclusive lock on the whole database file. A scan now commits only when it
  actually recorded an alert, and SQLite runs in WAL mode with `synchronous=NORMAL`. The
  endpoints still record alerts on scan, by design
  ([../business-rules/ALERTING.md](../business-rules/ALERTING.md)).
- **PERF-02** — *fixed.* FastAPI runs the (synchronous) endpoints on 40 threadpool
  workers, and each holds a connection for the length of its request, but the pool was left
  on SQLAlchemy's default 15 — so past 15 concurrent requests the surplus ones timed out
  with a 500. The pool is now sized from that same number: 20 kept open plus 20 overflow,
  40 threads to 40 connections.
- **PERF-03** — *fixed.* The LLM diagnosis call set no timeout, so the SDK defaults
  applied: a 600-second read timeout across 3 attempts — ~30 minutes — holding a worker
  and a pooled connection the entire time. The client now runs with a 30-second timeout
  and one retry, a 60-second worst case, and the handler hands its connection back
  before calling the provider, so a diagnosis in flight holds none
  ([../design/LLM_FEATURE.md](../design/LLM_FEATURE.md)).
- **PERF-04** — *fixed.* No foreign key and no filter column was indexed — SQLite creates
  neither on its own — so every list endpoint was a full table scan, and the alert dedup
  probe scanned the whole `alerts` table once per instance. Five indexes now cover the
  columns the API actually filters and sorts on; a sixth, on `alerts.isResolved`, was
  measured and rejected because it made the query it was meant to help slower
  ([../design/ERD.md § Indexes](../design/ERD.md#indexes)).
- **PERF-05** — *fixed.* Alert dedup ran a `SELECT` per instance and an `INSERT` per
  alert, so a scan's statement count grew with its result set. A scan now probes for
  existing unresolved alerts once for all its instances and writes the new ones in a
  single batched `INSERT` — an `ADMIN` warnings poll fell from 6 statements to 3, and a
  first scan from 14 to 8. The dedup rule itself is unchanged
  ([../business-rules/ALERTING.md](../business-rules/ALERTING.md)).
- **PERF-06** — *fixed.* The session factory used SQLAlchemy's default expiry, so a
  `commit()` expired every row the request had loaded and serialising the response
  re-`SELECT`ed each one — a wasted round trip per row returned. `expire_on_commit=False`
  removes them: an `ADMIN` warnings first scan fell from 8 statements to 4. Nothing relied
  on the expiry — the four services that want post-commit state call `db.refresh()`
  explicitly ([../design/DATABASE.md § 3](../design/DATABASE.md#3-the-session-factory)).

With PERF-05 and PERF-06 both closed, a monitoring scan costs the same number of
statements whether it returns 4 instances or 500. The remaining nine findings range from
six unbounded list endpoints (**PERF-07**) down to notes recorded deliberately rather than
as defects — the login KDF cost (**PERF-13**) is correct as written and should not be
changed.

Every figure is measured against the seeded demo database, not estimated; the method is at
the end of the document so any number can be reproduced. Six findings — PERF-01, PERF-02,
PERF-03, PERF-04, PERF-05 and PERF-06 — have been fixed; the rest are recorded and still
open.

## Related

| Document | Why |
|---|---|
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | The layering and session handling the findings sit in |
| [../design/DATABASE.md](../design/DATABASE.md) | The engine, pool and session factory behind PERF-02 and PERF-06 |
| [../design/ERD.md](../design/ERD.md) | The schema, and the indexes PERF-04 added to it |
| [../design/LLM_FEATURE.md](../design/LLM_FEATURE.md) | The diagnosis endpoint behind PERF-03 and PERF-14 |
| [../business-rules/ALERTING.md](../business-rules/ALERTING.md) | The dedup rule PERF-05 had to preserve, and did |
| [../api/CONVENTIONS.md](../api/CONVENTIONS.md) | The pagination convention PERF-07 would extend |
| [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) | Why a passing suite catches none of this |
| [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md) | Keeping this document current when a finding is fixed |
