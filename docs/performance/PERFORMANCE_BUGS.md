# Performance Bugs

A review of `app/` for defects that cost latency, throughput, or concurrency. Fifteen
findings, ranked by the load at which they start to hurt. Ten — [PERF-01](#perf-01)
through [PERF-10](#perf-10) — have since been fixed; the **Status** column below says
which are still open.

Nothing here is a functional bug — every one of the tests passes, and the API returns
correct answers. These are the places where it stops returning them *fast*, or stops
returning them *at all* under concurrency. (The suite has grown from 104 cases to 125
across these fixes; each finding below quotes the count at the time it landed.)

**Every number below was measured**, not estimated. The method is in
[§ How these were measured](#how-these-were-measured) so any of them can be reproduced or
challenged.

---

## Summary

| ID | Finding | Where | Severity | Status |
|---|---|---|---|---|
| [PERF-01](#perf-01) | Monitoring polls take an exclusive write lock on the whole database | `services/monitor_service.py` | Critical | **Fixed** |
| [PERF-02](#perf-02) | Connection pool (15) is smaller than request concurrency (40) | `database.py` | Critical | **Fixed** |
| [PERF-03](#perf-03) | LLM diagnosis can hold a worker and a connection for ~30 minutes | `services/llm_service.py` | Critical | **Fixed** |
| [PERF-04](#perf-04) | No index on any foreign key or filter column | `models/models.py` | High | **Fixed** |
| [PERF-05](#perf-05) | Alert dedup runs one SELECT per instance (N+1) | `services/monitor_service.py` | High | **Fixed** |
| [PERF-06](#perf-06) | `commit()` expires the result set, forcing a re-SELECT per row | `database.py` | High | **Fixed** |
| [PERF-07](#perf-07) | Six list endpoints have no pagination or limit | controllers, services | High | **Fixed** |
| [PERF-08](#perf-08) | Pagination count query carries every column and the `ORDER BY` | `services/instance_service.py` | Medium | **Fixed** |
| [PERF-09](#perf-09) | `list_alerts` joins `instances` even when the join is unused | `services/alert_service.py` | Medium | **Fixed** |
| [PERF-10](#perf-10) | Two queries of pure auth overhead on every request | `core/deps.py` | Medium | **Fixed** |
| [PERF-11](#perf-11) | Authorization check lazy-loads a relationship per request | `core/deps.py`, controllers | Medium | Open |
| [PERF-12](#perf-12) | Aggregates computed in Python over fully loaded rows | `services/client_service.py` | Medium | Open |
| [PERF-13](#perf-13) | PBKDF2 at 260,000 iterations dominates the login path | `core/security.py` | Low (by design) | Won't fix |
| [PERF-14](#perf-14) | A new Anthropic HTTP client is built per diagnosis request | `services/llm_service.py` | Low | Open |
| [PERF-15](#perf-15) | `create_all` and the seed probe run on every startup | `main.py`, `seed.py` | Low | Open |

---

## Critical

### PERF-01

**Every monitoring poll takes an exclusive write lock on the whole database.**
**Fixed** — see [The fix that landed](#the-fix-that-landed) at the end of this finding.

`GET /api/monitor/warnings`, `/errors` and `/long-stopped` are read-shaped endpoints that
`INSERT` alerts and then called `db.commit()` **unconditionally** —
[monitor_service.py](../../app/services/monitor_service.py). The commit fired even when
`_record_alert` recorded nothing, which after the first scan is the normal case: the
dedup guard ([../business-rules/ALERTING.md](../business-rules/ALERTING.md)) means a
repeat poll inserts nothing at all.

The engine ran on SQLite defaults. Measured against the real `monitoring.db` before the
fix:

```
journal_mode = delete
synchronous  = 2   (FULL)
busy_timeout = 5000
```

With a rollback journal, a write transaction locks the **entire database file**, not a
row or a table, and `synchronous=FULL` fsyncs on every commit. Concurrent readers get
`SQLITE_BUSY` and block for up to 5 seconds before failing.

This is the worst possible shape for a monitoring API: the three endpoints a dashboard
polls most often were the three that serialized every other request in the system.

**Why it mattered.** A dashboard refreshing every 10 seconds turned a read-mostly workload
into a write-mostly one, and each write stalled all readers for the duration of an fsync.

#### The fix that landed

Two of the three fixes originally proposed here were applied; the third was deliberately
not.

1. **Commit only when something changed.** `_record_alert` already returned `True`/`False`,
   so the three scans collect that and hand it to `_commit_if_recorded`
   ([monitor_service.py:70](../../app/services/monitor_service.py#L70)). A scan that opens
   no new alert never commits, and never takes a write lock. (The recording helper is
   `_record_alerts`, one call per scan, since [PERF-05](#perf-05); it returns the same
   flag.)

2. **WAL and a relaxed sync mode**, set on every SQLite connection by `_set_sqlite_pragmas`
   ([database.py:52](../../app/database.py#L52)):

   ```
   journal_mode = wal
   synchronous  = 1   (NORMAL)
   busy_timeout = 5000
   ```

   Readers now run against the last committed snapshot while a writer works, so the scan
   that *does* record an alert no longer blocks them either. The pragmas are guarded by
   `IS_SQLITE`, so a non-SQLite `DATABASE_URL` is untouched. WAL leaves `monitoring.db-wal`
   and `monitoring.db-shm` beside the database file; both are in `.gitignore`.

3. **Taking alert recording off the read path** — a `POST /api/monitor/scan` or a
   background task, with the three `GET`s becoming pure reads — was **not** done. It adds
   an endpoint and removes the auto-record-on-scan behaviour that
   [../business-rules/ALERTING.md § 2](../business-rules/ALERTING.md#2-detection-writes-alerts)
   documents as a deliberate concession to the assignment's shape, and both are out of
   scope. The `GET`s still write; they just no longer write *nothing* at the cost of a
   global lock.

Measured with the same `TestClient` harness as the rest of this document, one scan
followed by ten repeat polls of each endpoint:

| Endpoint | Commits before | Commits after |
|---|---|---|
| `/api/monitor/warnings` (4 instances) | 11 | 1 |
| `/api/monitor/errors` (2 instances) | 11 | 1 |
| `/api/monitor/long-stopped` (3 instances) | 11 | 1 |

The first scan still commits — it has real alerts to write. Every poll after it is a pure
read. All 104 functional tests pass unchanged.

What this did **not** fix at the time: the commit that does happen still expired the
result set ([PERF-06](#perf-06)), and the per-instance dedup `SELECT` it left in place was
still one statement per instance ([PERF-05](#perf-05)). Both have since been fixed. One
side effect of this fix is worth naming, because it changed what PERF-06 costs: a repeat
poll no longer commits, so it no longer expires anything either — after this landed, the
post-commit refreshes were confined to the scans that actually record an alert.

---

### PERF-02

**The connection pool is a third the size of the request concurrency.**
**Fixed** — see [The fix that landed](#the-fix-that-landed-1) at the end of this finding.

Every endpoint in `app/controllers/` is declared `def`, not `async def`. FastAPI therefore
runs each one in `run_in_threadpool`, and AnyIO's default limiter allows **40** such
workers concurrently.

The engine was created with no pool arguments, so it got `QueuePool` defaults — measured:

```
pool: QueuePool  size 5      (+ max_overflow 10  =  15 connections)
```

40 concurrent handlers, 15 connections. Request 16 onward blocks in `pool.connect()` for
30 seconds and then raises `TimeoutError: QueuePool limit of size 5 overflow 10 reached`.

**Why it mattered.** The failure mode is not slowness, it is a 500. And it appears only
under concurrency, so no functional test will ever catch it.

#### The fix that landed

The pool is now sized from the concurrency it has to serve, with the two numbers written
next to each other so the mismatch cannot come back
([database.py:21](../../app/database.py#L21)):

```python
MAX_CONCURRENT_REQUESTS = 40          # AnyIO's default threadpool limit
POOL_SIZE = MAX_CONCURRENT_REQUESTS // 2
MAX_OVERFLOW = MAX_CONCURRENT_REQUESTS - POOL_SIZE
```

20 connections kept open and 20 more opened on demand: **40 threads, 40 connections**. The
alternative — capping the threadpool at 15 to match the pool — was not taken; it would have
made the pool the limit on request concurrency for every endpoint, including the ones that
touch the database briefly or not at all.

`pool_pre_ping=True` goes with it: after a quiet period the pool holds connections the
server may have closed, and pre-ping replaces such a connection instead of failing the
request that borrowed it.

Two details worth knowing:

- The pool arguments are skipped when `DATABASE_URL` names an **in-memory** SQLite
  database. That URL gets a `SingletonThreadPool`, which has no `max_overflow`, and
  passing one raises `TypeError` at import. File-backed SQLite — the default, and what
  every deployment uses — gets `QueuePool` and is sized normally.
- Nothing in the test suite is affected: `tests/conftest.py` builds its own `StaticPool`
  engine and overrides `get_db`. All 104 tests pass unchanged.

Measured, 40 threads each borrowing a connection and holding it for 3 seconds, with
`pool_timeout` lowered to 2 seconds so the run finishes quickly:

| Pool | Served | Failed |
|---|---|---|
| Defaults (5 + 10 = 15) | 15 / 40 | 25 × `TimeoutError` |
| Sized (20 + 20 = 40) | 40 / 40 | 0 |

What this does **not** fix: a handler that holds its connection for minutes rather than
milliseconds still exhausts the pool — 40 slow LLM diagnoses would have done what 15 used
to. Sizing the pool buys headroom; it does not bound how long a request may keep a
connection. That bound is what [PERF-03](#perf-03) adds for the one handler that needed
it.

---

### PERF-03

**A single LLM diagnosis can hold a worker and a database connection for ~30 minutes.**
**Fixed** — see [The fix that landed](#the-fix-that-landed-2) at the end of this finding.

`llm_service.py` built its Anthropic client with no `timeout=` and no `max_retries=`, so
the SDK's own defaults applied. Measured (`anthropic 0.120.2`):

```
DEFAULT_TIMEOUT     Timeout(connect=5.0, read=600, write=600, pool=600)
DEFAULT_MAX_RETRIES 2
```

600-second read timeout across 3 attempts is roughly **30 minutes** worst case. For that
entire window the request held:

- one of the 40 threadpool slots ([PERF-02](#perf-02)), and
- one of the pool connections — `get_db` opens the session *before* the handler runs and
  closes it only after it returns, so the session was pinned across the whole network
  call even though the last query had finished before it started.

Enough slow diagnosis calls therefore exhaust the pool for **every** endpoint, including
`GET /`.

#### The fix that landed

Both halves were applied: bound the wait, and stop holding a connection through it.

1. **A timeout and a retry cap on the client**
   ([llm_service.py:23](../../app/services/llm_service.py#L23)):

   ```python
   TIMEOUT_SECONDS = 30.0
   MAX_RETRIES = 1
   ```

   passed to every `anthropic.Anthropic(...)` the service builds, on both the
   key-supplied and the environment-resolved branch. Worst case falls from ~30 minutes to
   **60 seconds** (2 attempts × 30 s). The numbers are a product decision, not a tuning
   one: a diagnosis that has not answered in 30 seconds is no longer useful to an
   operator reading an incident card, and the rule-based fallback — instant, and already
   the answer whenever no key is configured — is the better response past that point. One
   retry still absorbs a transient connection error.

2. **The connection goes back to the pool before the call**
   ([instance_controller.py:126](../../app/controllers/instance_controller.py#L126)). The
   handler loads the instance, runs the access check, loads the 10 alerts, and then calls
   `db.close()` before `llm_service.diagnose(...)`. `Session.close()` releases the
   transactional resources and *resets* the session rather than tearing it down, so the
   `db.close()` in `get_db`'s `finally` is a no-op; the rows it loaded are detached but
   **not** expired, so `instance.instanceName`, the alert fields the prompt renders, and
   the response body all keep reading from memory.

The fallback path is unaffected — it never touched the database either.

Measured, 20 concurrent diagnosis requests against the real engine with the provider call
stubbed to a barrier, so all 20 sit in the network call at the same instant:

| | Connections held during the provider call |
|---|---|
| Before | 20 / 20 |
| After | **0** |

| | Worst-case wait for one diagnosis |
|---|---|
| Before | 600 s read × 3 attempts ≈ 30 min |
| After | 30 s read × 2 attempts = **60 s** |

All 104 functional tests pass unchanged.

What this does **not** fix: the request still occupies one of the 40 threadpool workers
for the length of the call — bounded at 60 seconds now, but still held. Releasing that
too means `async def` plus `AsyncAnthropic`, which
[../design/LLM_FEATURE.md § 8](../design/LLM_FEATURE.md#8-known-limitations-and-future-work)
records as future work. The client is also still constructed per request
([PERF-14](#perf-14)).

---

## High

### PERF-04

**No index exists on any foreign key or filter column.**
**Fixed** — see [The fix that landed](#the-fix-that-landed-3) at the end of this finding.

`models/models.py` declared `index=True` on primary keys and on `members.email`. Nothing
else. SQLite does not index foreign keys automatically.

`EXPLAIN QUERY PLAN`, measured on the seeded schema before the fix:

| Query | Plan |
|---|---|
| Main instance list (`clientId IN (…) AND status = …`) | `SCAN instances` |
| `accessible_client_ids` (`clients WHERE managerId = ?`) | `SCAN clients` |
| Alert dedup (`instanceId`, `alertType`, `isResolved`) | `SCAN alerts` |
| `list_alerts` (join + order) | `SCAN alerts` + `USE TEMP B-TREE FOR ORDER BY` |

Every list endpoint is O(table). The `clients` scan runs on **every** request made by a
`CLIENT_MANAGER` ([PERF-10](#perf-10)); the `alerts` scan ran once per instance inside the
monitoring endpoints (the N+1 [PERF-05](#perf-05) has since batched), so the two compounded
into O(instances × alerts).

**Fix.** The columns that are actually filtered and sorted on:

| Table | Index |
|---|---|
| `instances` | `(clientId, status)`, `region`, `updatedAt` |
| `clients` | `managerId` |
| `alerts` | `(instanceId, alertType, isResolved)`, `detectedAt`, `isResolved` |

The composite `alerts` index is the important one — it turns the dedup probe from a table
scan into a single index seek.

#### The fix that landed

Five of the six indexes above were added; the sixth was measured and rejected.

**What was declared** — [models.py](../../app/models/models.py), as `index=True` on the
single columns and `__table_args__` on the two composites:

| Table | Index | Serves |
|---|---|---|
| `clients` | `managerId` | The `accessible_client_ids` lookup on every `CLIENT_MANAGER` request |
| `instances` | `(clientId, status)` | The scope filter on every list and monitoring query, with `?status=` beside it |
| `instances` | `region` | `GET /api/instances?region=` |
| `instances` | `updatedAt` | `?sort=-updatedAt` |
| `alerts` | `(instanceId, alertType, isResolved)` | The dedup probe, once per instance per scan |
| `alerts` | `detectedAt` | `ORDER BY detectedAt DESC`, the sort on every alert listing |

The composite on `instances` leads with `clientId` deliberately: `clientId` is filtered on
its own far more often than `status` is, so one index serves both shapes.

**`alerts.isResolved` was not added.** It looks obvious — it is a filter parameter — but
the column is a boolean whose rows are overwhelmingly `false`, and every query that filters
on it also sorts by `detectedAt`. Given the index, SQLite takes it, matches nearly the whole
table, and then still has to sort what it matched:

```
GET /api/alerts?isResolved=false, ADMIN

with ix_alerts_detectedAt only   SCAN alerts USING INDEX ix_alerts_detectedAt
                                 | SEARCH instances USING INTEGER PRIMARY KEY

plus ix_alerts_isResolved        SEARCH alerts USING INDEX ix_alerts_isResolved (isResolved=?)
                                 | SEARCH instances USING INTEGER PRIMARY KEY
                                 | USE TEMP B-TREE FOR ORDER BY
```

It trades an ordered scan for an unordered seek plus a sort, on the table that grows
fastest — and every index is also a write cost on every `INSERT`. It was left out.

**The indexes reach an existing database.** `Base.metadata.create_all` skips a table that
already exists, and its indexes with it, so declaring an index does nothing to a
`monitoring.db` created before the declaration — and the project has no migration step
([../design/ERD.md § Known Gaps](../design/ERD.md#known-gaps)). `lifespan`
([main.py:25](../../app/main.py#L25)) therefore follows `create_all` with one
`index.create(bind=engine, checkfirst=True)` per index in the metadata. It is idempotent,
and against the existing seeded `monitoring.db` it created all five and left the rest
untouched.

Measured — the same statements, on the same seeded data, with and without the indexes:

| Query | Plan before | Plan after |
|---|---|---|
| Instance list, scoped + `status` | `SCAN instances` | `SEARCH instances USING INDEX ix_instances_clientId_status (clientId=? AND status=?)` + `USE TEMP B-TREE FOR ORDER BY` |
| Instance list by `region` | `SCAN instances` | `SEARCH instances USING INDEX ix_instances_region (region=?)` |
| `accessible_client_ids` | `SCAN clients` | `SEARCH clients USING COVERING INDEX ix_clients_managerId (managerId=?)` |
| Alert dedup probe | `SCAN alerts` | `SEARCH alerts USING INDEX ix_alerts_instanceId_alertType_isResolved (instanceId=? AND alertType=? AND isResolved=?)` |
| `list_alerts`, `ADMIN` | `SCAN alerts` + `USE TEMP B-TREE FOR ORDER BY` | `SCAN alerts USING INDEX ix_alerts_detectedAt` — no sort step |
| Instance list, `sort=-updatedAt` | `SCAN instances` + `USE TEMP B-TREE FOR ORDER BY` | `SCAN instances USING INDEX ix_instances_updatedAt` — no sort step |
| Report status counts, scoped | `SCAN instances` + `USE TEMP B-TREE FOR GROUP BY` | `SEARCH instances USING COVERING INDEX ix_instances_clientId_status (clientId=?)` + the same `GROUP BY` sort |

Every plan that scanned a filtered column now seeks it, and the two `ORDER BY` temp
B-trees — the alert listing's `detectedAt` sort and `?sort=-updatedAt` — are gone.

One row of that table trades in the other direction, and is worth being explicit about: the
scoped instance list **gains** a `USE TEMP B-TREE FOR ORDER BY`. A table scan visits rows in
rowid order, so the default `ORDER BY id` came free with the scan; drive the lookup off
`ix_instances_clientId_status` instead and the matches arrive in index order and have to be
sorted. That is the right trade for the shape this API has — sorting the rows one client
owns is bounded by that client's instance count, while the scan it replaces is bounded by
the whole table — but on a small table, or a filter that matches most of it, it is close to
a wash.

All 104 functional tests pass unchanged.

What this does **not** fix. Two plans stayed `SCAN instances`, both on the `ADMIN` path
where there is no `clientId` filter to lead with:

- `check_warnings` — `cpuUsage >= 80 AND status = 'RUNNING'`. `cpuUsage` is not indexed,
  and a `>=` on a float makes a poor index anyway; the composite cannot help because its
  leading column is absent from the query.
- `check_long_stopped` — `status = 'STOPPED' AND updatedAt <= ?`. SQLite prefers the scan
  to a range seek plus a row lookup per hit. A `(status, updatedAt)` composite would change
  that, and was not added: the same scan under a `CLIENT_MANAGER` already uses
  `ix_instances_clientId_status`, and a third index on `instances` for the unscoped case
  alone did not earn its write cost.

Indexing also does nothing about the *number* of queries. It made the dedup probe a seek
rather than a scan, but left it one statement per instance — that is [PERF-05](#perf-05),
fixed separately and since. The count query still sorted in order to count
([PERF-08](#perf-08), fixed since), and `list_alerts` still joined `instances` when nothing
needed the join ([PERF-09](#perf-09), fixed since too).

---

### PERF-05

**Alert deduplication issues one SELECT per instance.**
**Fixed** — see [The fix that landed](#the-fix-that-landed-4) at the end of this finding.

`_record_alert` called `_has_unresolved_alert` inside a per-instance loop, and each call
was its own `SELECT … LIMIT 1`. [PERF-04](#perf-04) had already turned each one into an
index seek rather than a full `alerts` scan, but their *number* was unchanged: one round
trip per instance, and one `INSERT` per alert beside it.

Measured, `ADMIN GET /api/monitor/warnings` against the 16 seeded instances — **14
queries** for a response of 4 rows:

```
1 × SELECT members            (auth)
1 × SELECT instances          (the actual work)
4 × SELECT alerts             <- dedup probe, one per matching instance
4 × INSERT INTO alerts        <- one statement per alert
4 × SELECT instances          <- see PERF-06, fixed since
```

Two of those groups scale with the result size. At 500 warning instances this is 500
dedup probes plus 500 individual inserts.

#### The fix that landed

The dedup rule is unchanged — same guard, same `(instanceId, alertType, isResolved)`
condition, same behaviour through the API. What changed is that the whole scan is now
one probe and one insert instead of two statements per instance
([monitor_service.py:35](../../app/services/monitor_service.py#L35)):

1. **One dedup probe for the scan.** `_instances_with_unresolved_alert` selects
   `Alert.instanceId` for every id in the scan at once and returns them as a set;
   `_record_alerts` builds the new alerts from the instances missing from it. It is the
   same index seek [PERF-04](#perf-04) enabled, over an `IN` list rather than one id.

2. **One `INSERT` for the batch.** The inserts go through a Core
   `db.execute(insert(Alert), [...])` rather than `db.add_all`. That distinction is not
   stylistic: the ORM has to read back the generated `id` of every row it inserts, and
   SQLite's `RETURNING` does not guarantee the order rows come back in, so SQLAlchemy
   cannot correlate them and falls back to **one statement per object** — measured,
   `add_all` still emitted 4 `INSERT`s for 4 alerts. Nothing in a scan uses the alert
   rows once they are written (the endpoint returns instances), so the ids are not
   needed, and without them the batch goes out as a single `executemany`. `isResolved`
   and `detectedAt` still come from the column defaults declared on the model, evaluated
   per row exactly as before.

3. **The `IN` list is chunked** at `ID_BATCH_SIZE = 500`
   ([monitor_service.py:14](../../app/services/monitor_service.py#L14)). SQLite refuses
   a statement with more than 32,766 bind parameters, and these endpoints have no upper
   bound on how many instances they return ([PERF-07](#perf-07)) — one query per 500 ids
   keeps the statement preparable at any scan size while staying O(1) round trips for
   every realistic one.

`_commit_if_recorded` is untouched: `_record_alerts` returns whether it created anything,
and a scan that created nothing still ends without a commit ([PERF-01](#perf-01)).

Measured with the same statement-logging harness as the rest of this document, on the
same 16-instance seed:

| Request | Rows | Statements before | Statements after |
|---|---|---|---|
| `ADMIN /api/monitor/warnings`, first scan | 4 | 14 | **8** |
| `ADMIN /api/monitor/warnings`, repeat poll | 4 | 6 | **3** |
| `ADMIN /api/monitor/errors`, first scan | 2 | 8 | **6** |
| `ADMIN /api/monitor/errors`, repeat poll | 2 | 4 | **3** |
| `ADMIN /api/monitor/long-stopped`, first scan | 3 | 11 | **7** |
| `ADMIN /api/monitor/long-stopped`, repeat poll | 3 | 5 | **3** |
| `CLIENT_MANAGER /api/monitor/warnings`, first scan | 2 | 9 | **7** |
| `CLIENT_MANAGER /api/monitor/warnings`, repeat poll | 2 | 5 | **4** |

The `ADMIN` warnings scan, statement for statement, is now:

```
1 × SELECT members            (auth)
1 × SELECT instances          (the actual work)
1 × SELECT alerts             <- dedup probe, one for the whole scan
1 × INSERT INTO alerts        <- one executemany, 4 rows
4 × SELECT instances          <- see PERF-06, fixed since — the scan is 4 statements now
```

The two groups that scaled with the result set are now fixed at one statement each. At
500 warning instances the scan issues 3 statements plus the [PERF-06](#perf-06) refreshes
instead of 1,002 — and the repeat poll, which is the case a dashboard actually generates,
is 3 statements no matter how many instances match. (Those refreshes are gone too since
PERF-06 was fixed, which is why the "statements after" column above reads 4 rather than 8
on the current code.)

All 104 functional tests pass unchanged, including the dedup coverage in
[tests/test_member_c.py](../../tests/test_member_c.py): repeat scans that must not
duplicate, and the resolve-then-rescan that must open a fresh alert for one instance
while leaving the others deduplicated — the partial case that a batched probe has to get
right.

What this did **not** fix: the trailing per-row refresh, which was left as the only group
in that trace still scaling with the result set — that is [PERF-06](#perf-06), fixed since.
The endpoints remain unbounded in what they return ([PERF-07](#perf-07)).

---

### PERF-06

**`commit()` expires the result set, so serialization re-SELECTs every row.**
**Fixed** — see [The fix that landed](#the-fix-that-landed-5) at the end of this finding.

`SessionLocal` was built without `expire_on_commit=False`
([database.py](../../app/database.py)), so `db.commit()` marked every loaded object
expired. The monitoring endpoints commit and then **return** the instances they just
loaded — and Pydantic reading `instance.instanceName` for the response triggered a refresh
`SELECT` for each one.

This is the trailing `4 × SELECT instances` in the [PERF-05](#perf-05) trace — the one
group there that batching did not remove.

One wasted round trip per row returned, and the count grew with the result set: at 500
warning instances, a scan paid 500 refreshes to serialize rows it had already loaded.

**Fix.** `sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)`.
Nothing in this codebase relies on post-commit expiry — `update_status` and `resolve_alert`
already call `db.refresh()` explicitly where they want fresh state.

#### The fix that landed

The one-line fix, as proposed
([database.py:44](../../app/database.py#L44)):

```python
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
)
```

`tests/conftest.py` builds its own session factory and got the same argument, so the suite
exercises the session semantics the application runs on rather than SQLAlchemy's defaults.

**Nothing depends on the expiry it removes**, which is what makes this safe rather than
merely cheap. Four functions want state back from the database after their commit —
`create_instance`, `update_status`, `create_client` and `resolve_alert` — and every one of
them calls `db.refresh()` explicitly on the line after `db.commit()`. They were not relying
on the implicit reload; they were paying for it twice over on the default, since the refresh
they asked for made the expiry redundant. Measured, each of those endpoints issues exactly
the same statements it did before. Sessions are per-request — `get_db` opens one and closes
it after the response — so no unexpired value survives into another request.

Measured with the same statement-logging harness as the rest of this document, on the same
16-instance seed:

| Request | Rows | Statements before | Statements after |
|---|---|---|---|
| `ADMIN /api/monitor/warnings`, first scan | 4 | 8 | **4** |
| `ADMIN /api/monitor/errors`, first scan | 2 | 6 | **4** |
| `ADMIN /api/monitor/long-stopped`, first scan | 3 | 7 | **4** |
| `CLIENT_MANAGER /api/monitor/warnings`, first scan | 2 | 7 | **5** |
| `CLIENT_MANAGER /api/monitor/errors`, first scan | 2 | 7 | **5** |
| `CLIENT_MANAGER /api/monitor/long-stopped`, first scan | 2 | 7 | **5** |

The `ADMIN` warnings scan, statement for statement, is now:

```
1 × SELECT members            (auth)
1 × SELECT instances          (the actual work)
1 × SELECT alerts             <- dedup probe, one for the whole scan (PERF-05)
1 × INSERT INTO alerts        <- one executemany, 4 rows (PERF-05)
                              <- the 4 refreshes are gone
```

Four statements for a scan of any size. Together with [PERF-05](#perf-05) this closes the
last group in that trace that scaled with the result set: at 500 warning instances the
first scan now issues 4 statements rather than 1,502.

**One correction to the finding above**, which was written before [PERF-01](#perf-01)
landed. It claimed the waste "happens even when nothing was written", and quoted a
`CLIENT_MANAGER` repeat poll costing 7 queries with 0 inserts. That is no longer the
shape of a repeat poll: since PERF-01 a scan that records nothing does not commit, and
without a commit there is no expiry to pay for. Re-measured on the current code, a repeat
poll costs 3 statements as `ADMIN` and 4 as `CLIENT_MANAGER` — **with and without this
fix**. The refreshes this fix removes were confined to the first scan, the one that
actually writes. The finding was real and the fix is worth having; its blast radius was
smaller than the original text says.

The endpoints where the count is unchanged, measured rather than assumed:

| Request | Statements before | after |
|---|---|---|
| `POST /api/instances` | 4 | 4 |
| `PATCH /api/instances/1/status` | 5 | 5 |
| `PATCH /api/alerts/1/resolve` | 6 | 6 |
| `POST /api/clients` | 4 | 4 |
| `ADMIN /api/monitor/report` | 5 | 5 |

The four writes each end in an explicit `db.refresh()`, which is one `SELECT` either way.
`build_report` never commits, so it never had anything to expire.

All 104 functional tests pass unchanged — including the ones that read the session
directly after a request (`db.get(Instance, 1) is None` after a delete, the `updatedAt`
comparison across an idempotent update), which are the assertions a change to expiry
semantics would break first.

What this did **not** fix: the endpoints still returned every matching row
([PERF-07](#perf-07)), so the *response* still grew without bound even though the
statement count no longer did. That has since been fixed too.

---

### PERF-07

**Six list endpoints have no pagination and no limit.**
**Fixed** — see [The fix that landed](#the-fix-that-landed-6) at the end of this finding.

| Endpoint | Bound |
|---|---|
| `GET /api/instances` | paginated |
| `GET /api/alerts` | none |
| `GET /api/clients` | none |
| `GET /api/clients/{id}/instances` | none |
| `GET /api/monitor/warnings` / `/errors` / `/long-stopped` | none |
| `unresolvedAlerts` inside `GET /api/monitor/report` | none |

`alerts` is the fastest-growing table in the schema — the monitoring endpoints append to
it and nothing ever prunes it — and it backs the least bounded response in the API.
`GET /api/alerts` with no filters loads and serializes the entire table.

`build_report` compounds it: it materialises the full unresolved list and then uses it
only for `len(unresolved)` **and** ships the whole thing in the response body
([monitor_service.py:134](../../app/services/monitor_service.py#L134)).

**Fix.** Reuse the `PageResponse[T]` and `page`/`size` convention that
`GET /api/instances` already established, so this is a consistency fix as much as a
performance one. In `build_report`, take the count with `func.count()` and cap the
embedded list (e.g. the 20 most recent), with the full history behind `/api/alerts`.

> Changing these response shapes is a breaking API change — it belongs in
> [../api/CONVENTIONS.md](../api/CONVENTIONS.md) and
> [../api/ENDPOINTS.md](../api/ENDPOINTS.md) in the same commit.

#### The fix that landed

All of it, as proposed, plus two things the proposal did not anticipate.

**1. One pagination convention, in one module.** The bounds, the `page`/`size` query
pair and the counting moved into [app/pagination.py](../../app/pagination.py) and the
seven list endpoints share them. `GET /api/instances` was rewired through the same helper
rather than keeping its own copy, so `size` cannot end up capped at 100 on one route and
something else on the next. All six endpoints in the table above now answer with
`PageResponse[T]`, exactly as `GET /api/instances` always did.

**2. `build_report` counts instead of measuring a list**
([monitor_service.py](../../app/services/monitor_service.py), `build_report`).
`unresolvedAlertCount` comes from `func.count()`, and `unresolvedAlerts` is capped at
`REPORT_ALERT_LIMIT = 20`, newest first. The two fields no longer answer the same
question — the count is the true total and can exceed the array — which is a documented
behaviour change ([../api/ENDPOINTS.md](../api/ENDPOINTS.md)) rather than a silent one.

**3. Detection stayed unpaginated; only its response was bounded.** This is the part the
proposal did not raise, and it is the only place where the obvious implementation would
have been a functional regression. The three `/api/monitor/*` endpoints record an alert
for every instance meeting their condition
([../business-rules/ALERTING.md § 2](../business-rules/ALERTING.md#2-detection-writes-alerts)).
Recording only the page would make detection depend on how far a dashboard happened to
scroll — the instance on page 8 would never raise an alert. So `_scan`
([monitor_service.py](../../app/services/monitor_service.py)) walks the **whole** matching
set and keeps only the requested window.

**4. It walks that set in id-keyset batches rather than loading it.** `_scan` pulls
`WHERE id > :last ORDER BY id LIMIT 500` repeatedly, records each batch, counts it and
copies out any rows falling inside the page. That bounds what a scan holds in memory —
one batch plus one page — where before it held every matching instance at once; and
because the count and the page fall out of a walk the scan was making anyway, the
monitoring endpoints need no separate count query. `_instances_with_unresolved_alert` lost
its own internal chunking loop in the process: it is handed one batch and is one statement.

**5. A unique tiebreaker on every sort.** Pagination is only coherent if the ordering is
total. `GET /api/alerts` sorts by `detectedAt`, and a scan stamps every alert it records
with the same instant, so ties were the normal case rather than the exception; rows tied
on the sort key have no defined order, and a row could be served on two pages or on none
as a caller walked them. `id` is now the last sort key on both `/api/alerts` and
`/api/instances` (where `status`, `region` and `instanceType` are all heavily tied). This
costs nothing — see the plans below.

**What did not change:** the dedup rule, the scan-writes-alerts behaviour, the scope
filters, the sort whitelist, the cost and SLA endpoints (their arithmetic covers every
instance of a client, so those rows are loaded regardless and `costByInstance` /
`instanceDetails` stay complete).

##### Measured — the response

The point of the finding. Same `TestClient` harness as the rest of this document, seeded
demo data grown with extra RUNNING high-CPU instances so the listings have something to
bound, `ADMIN`, default page size:

| Request | Rows in body before | after | Body bytes before | after |
|---|---|---|---|---|
| `/api/monitor/warnings` | 704 | **10** | 165,974 | **2,423** |
| `/api/alerts` | 709 | **10** | 144,036 | **2,108** |
| `/api/clients/1/instances` | 703 | **10** | 165,734 | **2,416** |
| `/api/monitor/report` | 709 | **20** | 144,235 | **4,300** |

Before, every one of those grows with the table. After, none of them does — at 3,000
extra instances the same four bodies are 2,425 / 2,140 / 2,418 / 4,364 bytes, against
712,790 / 621,557 / 712,550 / 621,760 before.

##### Measured — the memory

Peak allocation during the single request, `tracemalloc` started around it on a warm
process, in KiB:

| Extra instances | `/api/monitor/warnings` | `/api/alerts` | `/api/clients/1/instances` | `/api/monitor/report` |
|---|---|---|---|---|
| 700 — before | 2,167 | 2,220 | 2,321 | 2,084 |
| 700 — after | 1,270 | **96** | **96** | **122** |
| 1,500 — before | 4,655 | 4,696 | 4,620 | 4,445 |
| 1,500 — after | 1,864 | **96** | **96** | **122** |
| 3,000 — before | 10,138 | 9,024 | 9,376 | 9,036 |
| 3,000 — after | 2,006 | **97** | **97** | **122** |

The three query-backed listings are flat: a page is a page whatever the table holds.
The warnings scan is *bounded* rather than flat, and settles around 2 MiB — that is
`ID_BATCH_SIZE = 500` instances in flight, which is the price of recording an alert for
every match. It stops growing; it does not become free.

##### Measured — the statements

Pagination costs a count query on the endpoints that gained one. On the 16-instance seed,
where every result already fitted on one page, that is the whole effect:

| Request | Role | Statements before | after |
|---|---|---|---|
| `/api/alerts` | `ADMIN` | 2 | 3 |
| `/api/clients` | `ADMIN` | 2 | 3 |
| `/api/clients/1/instances` | `ADMIN` | 3 | 4 |
| `/api/monitor/report` | `ADMIN` | 5 | 6 |
| `/api/instances` | `ADMIN` | 3 | 3 |
| `/api/monitor/warnings`, first scan | `ADMIN` | 4 | 4 |
| `/api/monitor/warnings`, repeat poll | `ADMIN` | 3 | 3 |

The monitoring endpoints are unchanged at seed scale because the keyset walk replaces the
single `SELECT` it used to issue rather than adding to it. At 704 matching instances they
cost 7 statements against 5 — three per 500-instance batch instead of one `SELECT` plus a
probe and an insert per batch. That is the trade this fix makes and it is worth stating
plainly: **two extra statements per 500 instances, in exchange for a response and a
working set that no longer grow at all.**

##### Measured — the plans

`EXPLAIN QUERY PLAN` on the seeded schema, for the two statements this fix introduced or
changed:

```
GET /api/instances count, before          CO-ROUTINE anon_1
                                          SEARCH instances USING INDEX ix_instances_clientId_status (clientId=?)
                                          USE TEMP B-TREE FOR ORDER BY
                                          SCAN anon_1

GET /api/instances count, after           SEARCH instances USING COVERING INDEX ix_instances_clientId_status (clientId=?)
```

That second row is [PERF-08](#perf-08), closed as a side effect — see there.

```
GET /api/alerts order, before             SCAN alerts USING INDEX ix_alerts_detectedAt
  (detectedAt only)                       SEARCH instances USING COVERING INDEX ix_instances_id

GET /api/alerts order, after              SCAN alerts USING INDEX ix_alerts_detectedAt
  (detectedAt, id tiebreaker)             SEARCH instances USING COVERING INDEX ix_instances_id
```

Identical, and still no `USE TEMP B-TREE FOR ORDER BY`. The tiebreaker is free because
SQLite holds a non-unique index in `(key, rowid)` order already, so
`ORDER BY detectedAt DESC, id DESC` is exactly a reverse scan of `ix_alerts_detectedAt` —
the ordered scan [PERF-04](#perf-04) bought is not given back.

The keyset batch inside a scan plans as
`SEARCH instances USING INTEGER PRIMARY KEY (rowid>?)`, which is a bounded range seek —
better than the `SCAN instances` [PERF-04](#perf-04) recorded for `check_warnings` and
could not improve, since the `LIMIT` now lets SQLite stop early.

##### Verification

**123 functional tests pass** — the 104 that existed, of which 14 were updated for the new
response shape, plus 19 new ones. The new cases pin the parts a reader would otherwise
have to take on trust: that pages partition a listing with no gaps or repeats even when
the sort key is heavily tied; that `total` counts the scoped, filtered set rather than the
table; that a page past the end is an empty `200`; that `size=101` is a `422`; that a scan
returning one instance per page still records alerts for all four matches; that the same
scans give identical instances and identical alert counts at batch sizes 1 and 3 as at
500; that the report's count keeps counting past the 20 alerts it embeds; and that the
cost and SLA responses still cover every instance rather than a page.

##### What this does not fix

- **The breaking change is real.** Six endpoints that returned a JSON array now return an
  envelope. Any existing client iterating the response has to read `.items`.
- **`GET /api/alerts` still joined `instances` when nothing needed the join**
  ([PERF-09](#perf-09)) — and the count query inherited that join too, so for an `ADMIN`
  the join was paid twice per request instead of once. Fixed since, which is exactly the
  leverage that doubling gave it.
- **`costByInstance` and `instanceDetails` remain unbounded.** They are the two remaining
  response arrays that grow with a client's instance count. Bounding them would mean
  changing what the numbers beside them mean, which is a product decision rather than a
  performance one.
- **`offset` is still `OFFSET`.** Deep paging re-walks the rows it skips, so page 500 of
  a listing costs what pages 1–500 would. The keyset walk inside `_scan` avoids this for
  the scans; the query-backed listings do not, and at this project's scale that is not
  worth the API change a cursor would need.

---

## Medium

### PERF-08

**The pagination count query carries every column and the `ORDER BY`.**
**Fixed** — closed by [PERF-07](#perf-07); see [The fix that landed](#the-fix-that-landed-7)
at the end of this finding.

`total = query.count()` at
[instance_service.py:73](../../app/services/instance_service.py#L73) wrapped the fully
built query — sort included. Measured SQL:

```sql
SELECT count(*) FROM (
  SELECT instances.id, instances."instanceName", instances.region, instances."instanceType",
         instances.status, instances."cpuUsage", instances."monthlyCost", instances."clientId",
         instances."launchedAt", instances."updatedAt"
  FROM instances WHERE instances."clientId" IN (?, ?)
  ORDER BY instances.id                                  -- sorting, in order to count rows
) AS anon_1
```

The sort cannot change a count. On any non-primary-key sort (`-cpuUsage`, `-updatedAt` —
both offered by the API) it forces a temp B-tree over the full filtered set, twice per
request.

**Fix.** Count before ordering:

```python
total = query.order_by(None).with_entities(func.count(Instance.id)).scalar()
```

#### The fix that landed

Exactly the line above, but not as its own change: [PERF-07](#perf-07) moved counting into
a shared `paginate()` helper ([app/pagination.py](../../app/pagination.py)) that six more
endpoints were about to start using, and writing the naive `query.count()` into it would
have spread this defect to all of them. The helper counts correctly, and
`GET /api/instances` was rewired through it, so this finding closed as a consequence
rather than on its own.

Measured — the same statement, on the same seeded data, before and after:

```sql
-- before
SELECT count(*) AS count_1 FROM (
  SELECT instances.id, instances."instanceName", instances.region, instances."instanceType",
         instances.status, instances."cpuUsage", instances."monthlyCost", instances."clientId",
         instances."launchedAt", instances."updatedAt"
  FROM instances WHERE instances."clientId" IN (?, ?, ?, ?, ?)
  ORDER BY instances."cpuUsage" DESC
) AS anon_1

-- after
SELECT count(instances.id) AS count_1
FROM instances WHERE instances."clientId" IN (?, ?, ?, ?, ?)
```

and the plans, on `?sort=-cpuUsage` as a `CLIENT_MANAGER`:

| | Plan |
|---|---|
| Before | `CO-ROUTINE anon_1` · `SEARCH instances USING INDEX ix_instances_clientId_status (clientId=?)` · `USE TEMP B-TREE FOR ORDER BY` · `SCAN anon_1` |
| After | `SEARCH instances USING COVERING INDEX ix_instances_clientId_status (clientId=?)` |

Four plan steps become one. The subquery and the temp B-tree are gone, and because the
count now selects a single indexed column the seek is **covering** — it answers from the
index without touching a row. The statement count per request is unchanged; what changed
is what that one statement does.

All 123 functional tests pass, including the sort and pagination coverage in
[tests/test_instances.py](../../tests/test_instances.py) that pins `total` across filters,
scoping and every offered sort key.

---

### PERF-09

**`list_alerts` joins `instances` even when the join is unused.**
**Fixed** — see [The fix that landed](#the-fix-that-landed-8) at the end of this finding.

[alert_service.py:19](../../app/services/alert_service.py#L19) joined unconditionally, but
the join exists only to reach `Instance.clientId` for the scope filter. For an `ADMIN`,
`client_ids is None` and the filter is never applied — the join is pure cost. Measured
plan: `SCAN alerts` + a per-row `SEARCH instances` + `USE TEMP B-TREE FOR ORDER BY`.

**Fix.** Move the join inside the `if client_ids is not None:` branch that already exists
one line below it.

Since [PERF-07](#perf-07) the endpoint also issues a count over the same query, so for an
`ADMIN` the unnecessary join is now paid twice per request rather than once. That raises
the value of this fix; it does not change its shape.

#### The fix that landed

Exactly the move proposed above
([alert_service.py:29](../../app/services/alert_service.py#L29)):

```python
query = db.query(Alert)
if client_ids is not None:
    query = query.join(Instance, Alert.instanceId == Instance.id).filter(
        Instance.clientId.in_(client_ids)
    )
```

An `ADMIN` now queries `alerts` alone; a `CLIENT_MANAGER` gets exactly the query they got
before. Everything else in the function — the four filters, the `detectedAt, id` ordering,
the `paginate()` call — is untouched.

**Why dropping an inner join is safe here**, which is the only part of this that needed
checking rather than measuring. An inner join is not purely a cost: it also *filters*, to
the rows whose `instanceId` matches a live instance. Removing it changes the answer if an
alert can outlive its instance — and for an `ADMIN`, who now has no join at all, such a row
would appear in the history where it used to be silently hidden. It cannot happen:
`Alert.instanceId` is `nullable=False`, the only writer of alerts is the monitoring scan
(which uses ids it has just read), and `Instance.alerts` is declared
`cascade="all, delete-orphan"`
([models.py:96](../../app/models/models.py#L96)), so `DELETE /api/instances/{id}` takes the
instance's alerts with it. Measured rather than assumed: after the three scans, deleting
instance 3 — `STOPPED`, and therefore deletable — takes its `LONG_STOPPED` alert with it,
and `GET /api/alerts` goes from 9 to 8. That is what
`test_deleting_an_instance_removes_its_alerts_from_the_history` in
[tests/test_alerts.py](../../tests/test_alerts.py) pins, because losing the cascade would
now be a *visible* bug rather than only a storage one.

##### Measured — the plans

The point of the finding. `EXPLAIN QUERY PLAN` on the two statements a request issues,
both variants run in the same process against the same seed with the pre-fix
unconditional join restored as a monkeypatch:

```
ADMIN, count      before   SCAN alerts USING COVERING INDEX ix_alerts_instanceId_alertType_isResolved
                           SEARCH instances USING COVERING INDEX ix_instances_id (id=? AND rowid=?)
                  after    SCAN alerts USING COVERING INDEX ix_alerts_id

ADMIN, page       before   SCAN alerts USING INDEX ix_alerts_detectedAt
                           SEARCH instances USING COVERING INDEX ix_instances_id (id=? AND rowid=?)
                  after    SCAN alerts USING INDEX ix_alerts_detectedAt
```

One index lookup into `instances` per row scanned, twice per request, gone from both.
`?isResolved=false` plans the same way. The `CLIENT_MANAGER` plans are unchanged in both
statements, which is the intent — that role still needs the join.

##### Measured — the latency

The statement *count* does not change: 3 for an `ADMIN`, 4 for a `CLIENT_MANAGER`, before
and after. What changes is what one of them does, so this is the one finding in this
document whose payoff is a wall-clock figure rather than a count. Median of 60 `ADMIN`
`GET /api/alerts` requests through `TestClient` on a warmed process, the demo seed grown
with synthetic alerts:

| Alerts in table | Before | After |
|---|---|---|
| 9 (the seed after three scans) | 4.0 ms | 4.0 ms |
| 5,009 | 4.4 ms | 4.3 ms |
| 20,009 | 5.7 ms | **4.5 ms** |

Consistent across three runs. At seed scale the difference is inside the noise and this
document should not claim otherwise; the join costs what the table costs, and `alerts` is
the table that grows. At 20,000 rows it is about a millisecond, roughly a fifth of the
request. Every one of those requests returned an identical `total` and identical ids under
both variants.

##### Verification

All 124 functional tests pass — the 123 that existed, unchanged, plus the cascade test
described above. The alert coverage in [tests/test_alerts.py](../../tests/test_alerts.py)
is what makes the unchanged 123 meaningful here: it pins the scoped `total`, the four
filters, the tie-broken ordering and the page partition for both roles, which is precisely
the behaviour a wrongly-dropped join would break.

##### One correction to the finding above

Its quoted plan — `SCAN alerts` + a per-row `SEARCH instances` + `USE TEMP B-TREE FOR
ORDER BY` — was measured before [PERF-04](#perf-04) and [PERF-07](#perf-07) landed, and
the temp B-tree is no longer part of it. `ix_alerts_detectedAt` gave the `ADMIN` listing
an ordered scan, and PERF-07's `id` tiebreaker kept it. Re-measured on the code as it
stood immediately before this fix, the `ADMIN` plan was `SCAN alerts USING INDEX
ix_alerts_detectedAt` + the per-row `SEARCH instances` — no sort step. The join was the
whole of the remaining waste, which is what this fix removes; the sort had already been
paid for elsewhere.

##### What this does not fix

The `CLIENT_MANAGER` path is untouched by design, and its plan still ends in
`USE TEMP B-TREE FOR ORDER BY`: driving the lookup off `ix_alerts_instanceId_alertType_isResolved`
delivers rows in index order, so the `detectedAt` sort has to be done. That is the same
trade [PERF-04](#perf-04) records for the scoped instance list, and it is a consequence of
scoping needing the join at all. [PERF-10](#perf-10) has since changed what the join is
given — a subquery rather than a list of ids — but not that it is needed: reaching
`Instance.clientId` from `alerts` still costs the join, and the sort step with it.

---

### PERF-10

**Every request pays two queries of pure authentication overhead.**
**Fixed** — see [The fix that landed](#the-fix-that-landed-9) at the end of this finding.

`get_current_member` does `db.get(Member, sub)`, and `accessible_client_ids` then scans
`clients` for the manager's ids ([deps.py:54](../../app/core/deps.py#L54)).

Measured, `CLIENT_MANAGER GET /api/alerts` — **3 queries, 2 of them overhead**:

```
SELECT members …                      <- auth
SELECT clients.id WHERE managerId = ? <- scope  (indexed since PERF-04)
SELECT alerts …                       <- the request
```

On the cheap endpoints, auth is the majority of the database work.

**Fix.** The client-id list does not need its own round trip — the scope can be expressed
as a join or a correlated subquery inside the query that is running anyway:

```python
query.filter(Instance.clientId.in_(
    select(Client.id).where(Client.managerId == member.id)
))
```

The `members` lookup is harder to remove safely (the token carries `role`, but re-reading
the row is what makes "member no longer exists" work), so it should stay — indexing
`clients.managerId` handles the other half.

#### The fix that landed

Exactly the shape proposed above. `accessible_client_ids` now *builds* the lookup instead
of running it ([deps.py:54](../../app/core/deps.py#L54)):

```python
def accessible_client_ids(member: Member) -> Select[tuple[int]] | None:
    if member.role == Role.ADMIN:
        return None
    scope = aliased(Client)
    return select(scope.id).where(scope.managerId == member.id)
```

The `db` parameter is gone — nothing is executed here any more — and with it the round
trip. Every call site already ended in an `IN`, so each one drops the `SELECT` straight
into the filter it was building:

```python
query = query.filter(Instance.clientId.in_(client_ids))
```

`None` still means "ADMIN, no filter", so the `if client_ids is not None:` branch in all
four services is unchanged, and so is every service signature apart from its type
(`Select[tuple[int]] | None` in place of `list[int] | None`).

Two details are deliberate:

- **The subquery is built over an alias.** `list_clients` filters `clients` by a subquery
  over `clients`; without the alias the two share a `FROM` element and the subquery is a
  candidate for being correlated away. With `aliased(Client)` it always renders its own
  `FROM clients AS clients_1` and cannot be.
- **The `-1` sentinel is gone.** Every call site read `.in_(client_ids or [-1])`, guarding
  the manager who has no clients — an empty list has no id to match. A subquery that
  selects no rows matches nothing on its own, so the guard has nothing left to guard. That
  path is now pinned by a test rather than by a sentinel; see *Verification* below.

The `members` lookup stays, as the finding said it should. One of the two overhead queries
was removable; this fix removes that one, and the auth cost of a `CLIENT_MANAGER` request
is now the same single lookup an `ADMIN` pays.

##### Measured — the query counts

The statement listener from [§ How these were measured](#how-these-were-measured), run
against a `git worktree` of the parent commit and the working tree by the same script.
Every endpoint is called twice and the second call is the one counted, so the monitoring
scans have already recorded their alerts rather than being counted mid-write:

| Request | Before | After |
|---|---|---|
| `ADMIN` — any of the six scoped list endpoints | 3 | 3 |
| `ADMIN` `GET /api/monitor/report` | 6 | 6 |
| `CLIENT_MANAGER` `GET /api/alerts` | 4 | **3** |
| `CLIENT_MANAGER` `GET /api/instances` | 4 | **3** |
| `CLIENT_MANAGER` `GET /api/clients` | 4 | **3** |
| `CLIENT_MANAGER` `GET /api/monitor/warnings` | 4 | **3** |
| `CLIENT_MANAGER` `GET /api/monitor/errors` | 4 | **3** |
| `CLIENT_MANAGER` `GET /api/monitor/long-stopped` | 4 | **3** |
| `CLIENT_MANAGER` `GET /api/monitor/report` | 7 | **6** |

One statement off every `CLIENT_MANAGER` request, and the `ADMIN` path untouched — it never
ran the scope query. The report drops one rather than five: the scope was a single lookup
feeding five statements, and it is now folded into each of them. Every paired run asserts
an identical `total`, an identical list of ids and, for the report, identical counts and
cost before reporting a number.

The trace the finding opens with is now two statements:

```
SELECT members …                                                     <- auth
SELECT alerts … WHERE instances.clientId IN (SELECT clients_1.id …)   <- the request
```

##### Measured — the plans

`EXPLAIN QUERY PLAN` on the statements that listener captured, run against the seeded
schema:

```
alerts count   before   SEARCH instances USING COVERING INDEX ix_instances_clientId_status (clientId=?)
                        SEARCH alerts USING COVERING INDEX ix_alerts_instanceId_alertType_isResolved (instanceId=?)

               after    SEARCH instances USING COVERING INDEX ix_instances_clientId_status (clientId=?)
                        LIST SUBQUERY 1
                          SEARCH clients_1 USING COVERING INDEX ix_clients_managerId (managerId=?)
                          CREATE BLOOM FILTER
                        SEARCH alerts USING COVERING INDEX ix_alerts_instanceId_alertType_isResolved (instanceId=?)
```

The outer plan is unchanged; what appears inside it is the scope lookup, and it is the same
covering-index seek on `ix_clients_managerId` that [PERF-04](#perf-04) bought for it when it
was a statement of its own. `LIST SUBQUERY`, not `CORRELATED LIST SUBQUERY` — SQLite
materialises it once per statement, not once per row. The scoped instance list and the
scoped client list plan the same way: outer plan identical, the same seek added inside.

One thing this removes that no plan shows: the old form carried **one bind parameter per
client the manager owns**. Manager 1 owns 5 clients in the seed, and the pre-fix statements
read `IN (?, ?, ?, ?, ?)` — the list grows with the assignment, against SQLite's cap of
32,766 bind parameters per statement. The subquery is one parameter whatever the manager
owns.

##### Verification

All 125 functional tests pass — the 124 that existed, unchanged, plus one added here. The
unchanged 124 are what make this safe: `test_client_list_is_scoped_by_role`,
`test_client_list_pagination_counts_only_the_callers_clients` and the scoped `total` and id
assertions across [tests/test_alerts.py](../../tests/test_alerts.py),
[tests/test_instances.py](../../tests/test_instances.py) and
[tests/test_member_c.py](../../tests/test_member_c.py) pin exactly what a mis-scoped filter
would break — one manager seeing another manager's rows.

The gap they left is the case the sentinel existed for, so it is now a test rather than a
`-1`: `test_a_manager_with_no_clients_sees_nothing` in
[tests/test_clients.py](../../tests/test_clients.py) registers a `CLIENT_MANAGER` with no
clients assigned and asserts that every scoped list, and the report, comes back empty. It
guards the scope mechanism rather than this fix in particular — losing the filter entirely
is the failure mode where an empty scope stops meaning "nothing" and starts meaning
"everything". Measured on both checkouts: identical empty responses before and after.

##### What this does not fix

The `members` lookup, by design — the first statement in the trace above is still there,
and re-reading the row is what makes an invalidated member's token stop working.

[PERF-11](#perf-11) is untouched: it is the other half of the original step 8, and the lazy
loads it describes are still one query each, so a single-object request like
`GET /api/instances/1` still issues three. What this fix changes for it is the shape of the
remedy that finding proposes — see there.

---

### PERF-11

**The authorization check lazy-loads a relationship on every request.**

`assert_client_access(member, instance.client)` needs a `Client` object, so accessing
`.client` fires a lazy load. Measured, `GET /api/instances/1` — 3 queries, the third being
that load. `resolve_alert` is worse: `alert.instance.client`
([alert_controller.py:57](../../app/controllers/alert_controller.py#L57)) is two chained
lazy loads.

**Fix.** `assert_client_access` reads exactly one field, `client.managerId`. An overload
taking the id — checked with an `EXISTS` over the scope subquery
[PERF-10](#perf-10) now returns — removes the load entirely. Where the object is genuinely
needed, `joinedload(Instance.client)` folds it into the original query.

(Written before PERF-10 landed, this proposed checking the id against "the accessible-id
set the request already computes". There is no such set any more — the scope is a `SELECT`
that rides inside the query it filters, and a single-object endpoint has no query for it to
ride in. The remedy is the same size, but it is a statement of its own rather than a free
comparison: one `EXISTS`, replacing one lazy load, and two of them for `resolve_alert`.)

---

### PERF-12

**Aggregates are computed in Python over fully loaded rows.**

`get_cost_forecast` ([client_service.py:104](../../app/services/client_service.py#L104))
loads every `RUNNING` instance of a client as a full ORM object, then does nothing with
those objects except count them by type. The response contains only counts and subtotals —
not a single instance field. A `GROUP BY instanceType` returning `(type, count)` gives the
same answer while transferring a handful of rows instead of all of them.

`get_client_cost` and `get_sla` also aggregate in Python, but legitimately: both embed
per-instance detail in the response, so the rows have to be loaded anyway. `get_client_cost`
could still take its `totalMonthlyCost` from `func.sum()` rather than re-summing in
Python, but the win is small.

**Fix.** Aggregate in SQL wherever the loaded rows do not appear in the response —
`get_cost_forecast` is the only clear case.

---

## Low

### PERF-13

**PBKDF2 at 260,000 iterations dominates the login path.** — *by design, no change
recommended*

`verify_password` ([security.py:22](../../app/core/security.py#L22)) runs 260,000 SHA-256
iterations, roughly 100–200 ms of CPU per `POST /api/auth/login`, occupying a threadpool
worker throughout.

This is correct and deliberate — it is the entire point of a password KDF, and lowering it
would be a security regression, not an optimization. It is recorded here because it makes
login by far the most expensive endpoint per call, and that fact belongs in a capacity
estimate. The test suite already works around it: `tests/conftest.py` memoises seed
hashing precisely because it otherwise dominates the suite's runtime.

If login volume ever justifies it, move verification to a `ProcessPoolExecutor` rather than
weakening the KDF.

---

### PERF-14

**A new Anthropic HTTP client is constructed per diagnosis request.**

[llm_service.py:57](../../app/services/llm_service.py#L57) builds
`anthropic.Anthropic(...)` on every call. Each construction creates a fresh `httpx` client
with its own connection pool, so every diagnosis pays a full TCP and TLS handshake with no
connection reuse — and the client is never closed, leaving sockets to the garbage
collector.

**Fix.** Build one client lazily at module level and reuse it, carrying the same
`timeout` and `max_retries` [PERF-03](#perf-03) added. The `import anthropic` inside the
function is fine as is (module imports are cached after the first call), but the client
should not follow it.

---

### PERF-15

**`create_all` and the seed probe run on every startup.**

The lifespan hook ([main.py:26](../../app/main.py#L26)) runs `Base.metadata.create_all`
and `seed()`, which opens with `SELECT members LIMIT 1`.

For a long-lived `uvicorn` process this is negligible — once, at boot. It is listed
because of `vercel.json`: on a serverless deployment **every cold start** pays it, against
a filesystem that does not persist between invocations, so the database is rebuilt and
re-seeded — including three PBKDF2 hashes at 260,000 iterations ([PERF-13](#perf-13)) —
before the first request is served.

**Fix.** For the demo deployment, none needed. For anything real, schema creation belongs
in a migration step and seeding behind an explicit env flag.

---

## Suggested order of work

Ordered by benefit per unit of risk, not by severity.

| # | Change | Findings closed | Risk |
|---|---|---|---|
| 1 | Add the missing indexes | [PERF-04](#perf-04) | None — additive — **done** |
| 2 | `expire_on_commit=False` | [PERF-06](#perf-06) | Low — **done** |
| 3 | WAL + `synchronous=NORMAL`; commit only when something changed | [PERF-01](#perf-01) | Low — **done** |
| 4 | Explicit pool sizing | [PERF-02](#perf-02) | Low — **done** |
| 5 | Timeout and retry cap on the Anthropic client, and the session released before the call | [PERF-03](#perf-03) | Low — **done** |
| 6 | Batch the alert dedup | [PERF-05](#perf-05) | Medium — touches the dedup rule — **done** |
| 7 | Count without the sort | [PERF-08](#perf-08) | Low — **done**, with step 9 |
| 8a | Conditional join | [PERF-09](#perf-09) | Low — **done** |
| 8b | Scope filter as a subquery | [PERF-10](#perf-10) | Medium — **done** |
| 8c | Drop the lazy loads | [PERF-11](#perf-11) | Medium |
| 9 | Paginate the remaining list endpoints | [PERF-07](#perf-07) | **Breaking** — API contract — **done** |

Steps 1–5 are schema and configuration; none of them changes any documented behaviour. Step 6
touched a rule documented in [../business-rules/ALERTING.md](../business-rules/ALERTING.md)
and kept the dedup guarantee intact — same guard, fewer statements. Step 9 changed six
response shapes and landed with [../api/CONVENTIONS.md](../api/CONVENTIONS.md),
[../api/ENDPOINTS.md](../api/ENDPOINTS.md) and
[../business-rules/ALERTING.md](../business-rules/ALERTING.md) in the same commit; it took
step 7 with it, because the shared counting helper it introduced had to count correctly
before six more endpoints started calling it.

The order above was written before any of this landed, and step 9 ran out of turn: it was
taken last as planned, but its own prerequisite — one place for the `page`/`size`
convention to live — made step 7 free, so the two closed together. Step 8 then split three
ways. The conditional join is a self-contained move of two lines with no effect on any
other finding, so it was taken on its own as **8a** and rated Low rather than Medium — the
risk in the original step 8 lives entirely in the auth-path changes, which rewrite how
scoping reaches the query. Those changes then split again: **8b** rewrites how the scope
*is expressed* and touches every list endpoint, **8c** rewrites how a *single object* is
authorized and touches none of them, and neither needs the other. 8b is done; what remains
is **8c**, and it is worth noting that 8b removed the thing 8c was originally going to
lean on — see [PERF-11](#perf-11).

---

## How these were measured

Every figure in this document came from instrumenting the app itself, against the
in-memory database seeded with the same demo data the test suite uses
([../demo/SEED_DATA.md](../demo/SEED_DATA.md)) — 3 members, 10 clients, 15 instances.
(Earlier revisions of this document said 16. The seed has always built 15; the count is
corrected here and the figures it appears beside are unaffected, since every one of them
was read off a run rather than derived from it.)

**Query counts** — a SQLAlchemy `before_cursor_execute` listener attached to the engine,
logging every statement while driving endpoints through `TestClient` as both `ADMIN` and
`CLIENT_MANAGER`:

```python
@event.listens_for(engine, "before_cursor_execute")
def record(conn, cursor, statement, params, context, executemany):
    log.append(" ".join(statement.split()))
```

The before/after counts under [PERF-05](#perf-05) come from that same listener with the
pre-fix `_record_alerts` — the per-instance loop, restored as a monkeypatch — swapped in
for one half of each pair, so both columns are measured on the same seed in the same
process rather than one being remembered. The claim that `db.add_all` does *not* batch on
SQLite is read off the listener too: `executemany` is `True` on those inserts, yet it
fires once per row, because SQLAlchemy cannot correlate SQLite's `RETURNING` rows back to
the objects it inserted. The chunked `IN` list was checked by driving the scans, the
repeat polls and the resolve-then-rescan path with `ID_BATCH_SIZE` forced to 1, 2 and 3
against the default 500: identical instances, identical alert counts, identical dedup
outcome at every size.

The before/after counts under [PERF-06](#perf-06) come from the same listener, run twice
in one process over two session factories built on the same seed — one with
`expire_on_commit=True`, the SQLAlchemy default and the schema as it was, one with it
`False` — so both columns are measured rather than one being remembered. Each pair gets a
fresh in-memory database, and each endpoint is driven twice: a first scan, which records
alerts and therefore commits, and a repeat poll, which does not. That second call is what
showed the finding's "even when nothing was written" paragraph to be stale since
[PERF-01](#perf-01) — the repeat poll's count is identical under both settings. The
unchanged rows in the second table there (`POST /api/instances`, the two `PATCH`es,
`POST /api/clients`, the report) were measured the same way rather than reasoned about.

The before/after numbers under [PERF-07](#perf-07) and [PERF-08](#perf-08) come from that
same listener run against **two checkouts** rather than two factories in one process: the
change alters response shapes, so a single process cannot host both. A `git worktree` of
the parent commit and the working tree were driven by the same script, which reports
whichever shape the checkout it is running in returns. The response-size and memory
figures come from the same pair — `len(response.content)` for the body, and
`tracemalloc.get_traced_memory()` started immediately around one already-warmed request
for the peak, so what it reports is that request's own allocation and not the process
baseline. The scale rows were produced by seeding the demo data and then bulk-inserting
700, 1,500 or 3,000 additional RUNNING instances at 95% CPU against client 1, so that the
same rows are matched by the warnings scan, carried by the alert history once scanned, and
listed by that client's instances endpoint.

The before/after counts under [PERF-10](#perf-10) come from that same listener run against
**two checkouts**, as [PERF-07](#perf-07)'s did — a `git worktree` of the parent commit and
the working tree, driven by the same script. Two checkouts rather than two factories in one
process because the change is to a function signature, not to a value that can be swapped:
`accessible_client_ids` loses its `db` parameter, so no monkeypatch can host both variants
beside each other. Each endpoint is requested twice and the second request is the counted
one, so a monitoring scan is counted as the repeat poll it will be in practice rather than
on the call that records its alerts. The script compares `total`, the returned ids and the
report's counts across the two checkouts before reporting any count, and the empty-scope
run described under that finding was driven the same way.

The before/after plans and latencies under [PERF-09](#perf-09) come from that listener
again, with the pre-fix `list_alerts` — the unconditional join, restored as a monkeypatch —
swapped in for one half of each pair, so both columns are measured in the same process on
the same seed. The latency rows are the median of 60 `TestClient` requests after 10
warm-up ones, at three table sizes: the seed's 9 alerts, and that seed bulk-loaded with
5,000 and 20,000 further alerts spread round-robin across the instances that exist. Every
paired run asserts an identical `total` and an identical list of ids before reporting a
time, which is also how the first attempt at this measurement caught itself: seeding
synthetic alerts against a hard-coded `instanceId` range of 1–16 produced 312 rows
pointing at a 16th instance that does not exist, and the two variants then disagreed by
exactly those rows — the inner join hiding them, the fixed version listing them. That is
the orphan case the finding has to rule out, manufactured by accident; ruling it out for
real is the cascade check above.

**Query plans** — `EXPLAIN QUERY PLAN` on the statements that listener captured, run
against the seeded schema. The before/after pairs under [PERF-04](#perf-04) come from two
engines built in the same process on that same seed — one from the metadata as it stands,
one with the six indexes discarded from the metadata before `create_all`, which is the
schema as it was — so both columns are measured rather than one being remembered. Dropping
the indexes from a live connection instead does *not* work: the plans come back unchanged,
because SQLite is still answering from the schema it prepared against.

**Pool exhaustion** — 40 threads against the real `monitoring.db`, each borrowing a
connection from a `create_engine(...)` pool and holding it for 3 seconds while the others
queue, `pool_timeout` lowered from 30 s to 2 s so a run takes seconds rather than minutes.
Counting successes and `TimeoutError`s under the default pool and the sized one is the
before/after table under [PERF-02](#perf-02).

**Engine and SQLite settings** — read from the real `monitoring.db` engine:
`type(engine.pool).__name__`, `engine.pool.size()`, and `PRAGMA journal_mode` /
`synchronous` / `busy_timeout`. The journal and sync figures quoted under
[PERF-01](#perf-01) are the pre-fix ones; the same three pragmas now read `wal` / `1` /
`5000`. The threadpool figure under [PERF-02](#perf-02) is
`anyio.to_thread.current_default_thread_limiter().total_tokens`, and its pool sizes came
from `engine.pool.size()` and `engine.pool._max_overflow` — 5 / 10 before, 20 / 20 now.

**Commit counts** — a `commit` event listener on the engine
(`@event.listens_for(engine, "commit")`), counting commits while driving one scan followed
by ten repeat polls of each monitoring endpoint through `TestClient` as `ADMIN`. This is
what the before/after table under [PERF-01](#perf-01) reports.

**SDK defaults** — read from the installed package, `anthropic 0.120.2`:
`anthropic._constants.DEFAULT_TIMEOUT` and `DEFAULT_MAX_RETRIES`. The worst-case
waits under [PERF-03](#perf-03) are those two against the module's `TIMEOUT_SECONDS`
and `MAX_RETRIES`, read back off a constructed client (`client.timeout`,
`client.max_retries`) to confirm the SDK took them.

**Connections held across the provider call** — 20 concurrent
`GET /api/instances/5/diagnosis` requests through `TestClient` against a file-backed
engine, with `_llm_diagnosis` replaced by a `threading.Barrier` so that all 20 sit in
the stand-in for the network call at the same instant; one of them reads
`engine.pool.checkedout()` there. Running it with and without the early `db.close()`
is the before/after table under [PERF-03](#perf-03).

Caveats worth stating: most counts come from the 15-instance seed, so absolute numbers are
small — what matters is which of them **scale with the result set**. Nothing measured here
still does. [PERF-05](#perf-05) and [PERF-06](#perf-06) made the statement count grow with
the result, and [PERF-07](#perf-07) made the response and the working set grow with it;
all three are fixed, and the grown-database rows under PERF-07 are there precisely because
the seed is too small to show the difference. [PERF-10](#perf-10) scaled with something
else again — the caller's client assignment, one bind parameter per client, which no
result-set figure would have shown; it is fixed, and the seed is too small to show that
either, so the finding argues it from the statement shape rather than from a number. What
remains unbounded by measurement rather than by fix is deep `OFFSET` paging and the two per-instance arrays in the cost and SLA
responses, both recorded under [PERF-07](#perf-07). [PERF-09](#perf-09) is the exception
to the "counts, not times" rule: it removes work from inside a statement without changing
how many statements run, so a wall-clock figure is the only thing that can show it, and
it is reported at a table size where that figure is larger than the noise. The query plans are SQLite's; a
different backend would plan differently, and would choose its own indexes from the ones
[PERF-04](#perf-04) declares. No HTTP load test was run: [PERF-02](#perf-02) was reproduced
at the connection-pool level rather than through the API, and the 30-minute figure in
[PERF-03](#perf-03) is derived from the SDK's configured limits rather than from an
observed timeout — its connection-hold counts, however, come from real requests
through the app.

---

## Related

| Document | Why |
|---|---|
| [README.md](README.md) | Performance index |
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | The layering and session handling these findings sit in |
| [../design/ERD.md](../design/ERD.md) | The schema that [PERF-04](#perf-04) adds indexes to |
| [../design/LLM_FEATURE.md](../design/LLM_FEATURE.md) | The diagnosis endpoint of [PERF-03](#perf-03) and [PERF-14](#perf-14) |
| [../business-rules/ALERTING.md](../business-rules/ALERTING.md) | The dedup rule [PERF-05](#perf-05) must preserve, and why [PERF-07](#perf-07) pages a scan's response but not its detection |
| [../api/CONVENTIONS.md](../api/CONVENTIONS.md) | The pagination convention [PERF-07](#perf-07) extended to every list endpoint |
| [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) | Why none of these are caught today |
| [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md) | Updating this document alongside a fix |
| [../changelog/CHANGELOG.md](../changelog/CHANGELOG.md) | When each fix landed |
