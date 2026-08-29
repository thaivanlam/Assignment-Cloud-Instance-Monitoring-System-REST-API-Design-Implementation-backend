# Performance

Findings on latency, throughput, and concurrency in `app/` — what is slow, why, and what
it would take to fix.

| Document | Contents |
|---|---|
| [PERFORMANCE_BUGS.md](PERFORMANCE_BUGS.md) | 15 measured findings ranked by severity, each with cause, evidence, and fix; a suggested order of work; the measurement method |

## The short version

Everything in `PERFORMANCE_BUGS.md` is a performance defect, not a functional one — the
104 tests pass and the API returns correct answers throughout. Three findings are rated
critical:

- **PERF-01** — the three `/api/monitor/*` endpoints are `GET`s that write and commit, and
  SQLite runs with a rollback journal, so every dashboard poll takes an exclusive lock on
  the whole database file.
- **PERF-02** — FastAPI runs the (synchronous) endpoints on 40 threadpool workers against
  a connection pool of 15. Past 15 concurrent requests the surplus ones time out with a
  500.
- **PERF-03** — the LLM diagnosis call sets no timeout, so the SDK defaults apply: a
  600-second read timeout across 3 attempts, holding a worker and a connection the entire
  time.

The remaining twelve range from missing indexes on every foreign key (**PERF-04**) down to
notes recorded deliberately rather than as defects — the login KDF cost (**PERF-13**) is
correct as written and should not be changed.

Every figure is measured against the seeded demo database, not estimated; the method is at
the end of the document so any number can be reproduced.

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
