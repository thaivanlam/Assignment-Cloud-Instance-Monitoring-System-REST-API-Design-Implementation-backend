# Performance

Findings on latency, throughput, and concurrency in `app/` — what is slow, why, and what
it would take to fix.

| Document | Contents |
|---|---|
| [PERFORMANCE_BUGS.md](PERFORMANCE_BUGS.md) | 15 measured findings ranked by severity, each with cause, evidence, and fix; a **Status** column saying which are fixed; a suggested order of work; the measurement method |

## The short version

Everything in `PERFORMANCE_BUGS.md` is a performance defect, not a functional one — the
104 tests pass and the API returns correct answers throughout. Three findings are rated
critical:

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
- **PERF-03** — the LLM diagnosis call sets no timeout, so the SDK defaults apply: a
  600-second read timeout across 3 attempts, holding a worker and a connection the entire
  time.

The remaining twelve range from missing indexes on every foreign key (**PERF-04**) down to
notes recorded deliberately rather than as defects — the login KDF cost (**PERF-13**) is
correct as written and should not be changed.

Every figure is measured against the seeded demo database, not estimated; the method is at
the end of the document so any number can be reproduced. Two findings, PERF-01 and
PERF-02, have been fixed; the rest are recorded and still open.

## Related

| Document | Why |
|---|---|
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | The layering and session handling the findings sit in |
| [../design/ERD.md](../design/ERD.md) | The schema PERF-04 would add indexes to |
| [../design/LLM_FEATURE.md](../design/LLM_FEATURE.md) | The diagnosis endpoint behind PERF-03 and PERF-14 |
| [../business-rules/ALERTING.md](../business-rules/ALERTING.md) | The dedup rule PERF-05 must preserve |
| [../api/CONVENTIONS.md](../api/CONVENTIONS.md) | The pagination convention PERF-07 would extend |
| [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) | Why a passing suite catches none of this |
| [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md) | Keeping this document current when a finding is fixed |
