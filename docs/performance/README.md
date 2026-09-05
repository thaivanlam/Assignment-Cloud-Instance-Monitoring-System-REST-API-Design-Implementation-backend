# Performance

Findings on latency, throughput, and concurrency in `app/` — what is slow, why, and what
it would take to fix.

| Document | Contents |
|---|---|
| [PERFORMANCE_BUGS.md](PERFORMANCE_BUGS.md) | 15 measured findings ranked by severity, each with cause, evidence, and fix; a **Status** column saying which are fixed — 11 of 15 so far; a suggested order of work; the measurement method |

## The short version

Everything in `PERFORMANCE_BUGS.md` is a performance defect, not a functional one — the
tests pass and the API returns correct answers throughout. Three findings are rated
critical, and all three are now fixed, as are all four high-severity ones and the first
four medium:

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

- **PERF-07** — *fixed.* Six of the seven list endpoints returned every matching row, so
  the response grew with the table on `alerts`, which nothing prunes — and the report
  serialised every unresolved alert purely to report their number. All seven now share one
  `page`/`size` convention ([app/pagination.py](../../app/pagination.py)) and answer with
  `PageResponse`; the report counts in SQL and embeds the 20 most recent. Measured on a
  grown database, `GET /api/alerts` fell from 709 rows and 144 KB to 10 rows and 2 KB, and
  its peak allocation stopped growing with the table — 96 KiB at 700 extra instances and
  still 97 KiB at 3,000, against 2.2 MB and 9.0 MB before. The monitoring scans still
  detect over **every** match and page only their response, which is the one thing the
  obvious implementation would have got wrong
  ([../business-rules/ALERTING.md § 2](../business-rules/ALERTING.md#2-detection-writes-alerts)).
  This is a **breaking** change to those six response shapes.
- **PERF-08** — *fixed*, as a consequence of PERF-07. `total = query.count()` wrapped the
  whole built query, so the database sorted the full filtered set in order to count it.
  The shared `paginate()` helper counts before ordering and over the primary key alone,
  which was not optional: writing the old form into a helper six more endpoints were about
  to call would have spread the defect. Four plan steps — a co-routine subquery, an index
  search, a temp B-tree and a scan — collapse to one covering index seek.
- **PERF-09** — *fixed.* `GET /api/alerts` joined `instances` on every request, but the
  join exists only to reach `Instance.clientId` for a `CLIENT_MANAGER`'s scope — an
  `ADMIN` has no scope to apply and was paying an index lookup per row scanned, twice per
  request since PERF-07 added the count query. The join is now made inside the branch that
  needs it. Dropping an inner join changes an answer if a row can be orphaned, so that was
  checked rather than assumed: `Instance.alerts` cascades its delete, no alert outlives its
  instance, and a test now pins it. The `ADMIN` plans lose the per-row `SEARCH instances`
  from both statements, and at 20,000 alerts the request falls from 5.7 ms to 4.5 ms.
- **PERF-10** — *fixed.* A `CLIENT_MANAGER` request ran a query purely to fetch the ids of
  the clients they manage, and then spent them as an `IN` list in the query it was about to
  run anyway. That scope is now a `SELECT` handed to the same `IN`, resolved inside the
  statement instead of before it: every `CLIENT_MANAGER` list endpoint fell from 4
  statements to 3 and the report from 7 to 6, with the `ADMIN` path and every plan
  unchanged. It also removes a bind parameter per client the manager owns. The `members`
  lookup stays — re-reading the row is what makes a deleted member's token stop working
  ([../business-rules/AUTHORIZATION.md § 2.1](../business-rules/AUTHORIZATION.md#21-list-endpoints--filter-at-the-query)).
- **PERF-11** — *fixed.* The other half of the auth path: a single-object endpoint reached
  `instance.client` to compare one integer, `managerId`, which fetched a whole `clients`
  row per request — and two rows on `PATCH /api/alerts/{id}/resolve`, which walked
  `alert.instance.client`. A second guard beside `assert_client_access` takes the client
  *id* the caller already holds and asks the PERF-10 scope whether it is in range, as one
  `EXISTS`; the alert's instance now arrives with the alert instead of on a load of its
  own. Every single-object request an `ADMIN` makes loses a statement — the loads fed a
  check an `ADMIN` skips — and `resolve_alert` loses two; a `CLIENT_MANAGER` trades a
  fetched-and-hydrated row for a boolean, and loses one on the alert path
  ([../business-rules/AUTHORIZATION.md § 2.2](../business-rules/AUTHORIZATION.md#22-single-resource-endpoints--check-after-load)).

With PERF-05, PERF-06 and PERF-07 closed, neither a monitoring scan's statement count nor
any list endpoint's response grows with the result set. The remaining four findings are
smaller: aggregation done in Python (**PERF-12**), a client rebuilt per LLM request
(**PERF-14**), startup work repeated on every boot (**PERF-15**) — and one recorded
deliberately rather than as a defect, the login KDF cost (**PERF-13**), which is correct as
written and should not be changed.

Every figure is measured against the seeded demo database — or, where the seed is too
small to show a difference, against that database grown with several thousand extra
instances — not estimated; the method is at the end of the document so any number can be
reproduced. Eleven findings, PERF-01 through PERF-11, have been fixed; the rest are
recorded and still open. PERF-09 is the one whose payoff is a wall-clock number rather than a
statement count — it removes work from inside a query without changing how many run.

## Related

| Document | Why |
|---|---|
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | The layering and session handling the findings sit in |
| [../design/DATABASE.md](../design/DATABASE.md) | The engine, pool and session factory behind PERF-02 and PERF-06 |
| [../design/ERD.md](../design/ERD.md) | The schema, and the indexes PERF-04 added to it |
| [../design/LLM_FEATURE.md](../design/LLM_FEATURE.md) | The diagnosis endpoint behind PERF-03 and PERF-14 |
| [../business-rules/ALERTING.md](../business-rules/ALERTING.md) | The dedup rule PERF-05 had to preserve, and why PERF-07 pages a scan's response but not its detection |
| [../api/CONVENTIONS.md](../api/CONVENTIONS.md) | The pagination convention PERF-07 extended to every list endpoint |
| [../security/README.md](../security/README.md) | The sibling register — the same codebase reviewed for what it exposes rather than what it costs |
| [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) | Why a passing suite catches none of this |
| [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md) | Keeping this document current when a finding is fixed |
