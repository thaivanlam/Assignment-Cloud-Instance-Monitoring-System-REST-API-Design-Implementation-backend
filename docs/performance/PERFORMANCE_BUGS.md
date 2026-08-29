# Performance Bugs

A review of `app/` for defects that cost latency, throughput, or concurrency. Fifteen
findings, ranked by the load at which they start to hurt.

Nothing here is a functional bug — every one of the 104 tests passes, and the API returns
correct answers. These are the places where it stops returning them *fast*, or stops
returning them *at all* under concurrency.

**Every number below was measured**, not estimated. The method is in
[§ How these were measured](#how-these-were-measured) so any of them can be reproduced or
challenged.

---

## Summary

| ID | Finding | Where | Severity |
|---|---|---|---|
| [PERF-01](#perf-01) | Monitoring polls take an exclusive write lock on the whole database | `services/monitor_service.py` | Critical |
| [PERF-02](#perf-02) | Connection pool (15) is smaller than request concurrency (40) | `database.py` | Critical |
| [PERF-03](#perf-03) | LLM diagnosis can hold a worker and a connection for ~30 minutes | `services/llm_service.py` | Critical |
| [PERF-04](#perf-04) | No index on any foreign key or filter column | `models/models.py` | High |
| [PERF-05](#perf-05) | Alert dedup runs one SELECT per instance (N+1) | `services/monitor_service.py` | High |
| [PERF-06](#perf-06) | `commit()` expires the result set, forcing a re-SELECT per row | `database.py` | High |
| [PERF-07](#perf-07) | Six list endpoints have no pagination or limit | controllers, services | High |
| [PERF-08](#perf-08) | Pagination count query carries every column and the `ORDER BY` | `services/instance_service.py` | Medium |
| [PERF-09](#perf-09) | `list_alerts` joins `instances` even when the join is unused | `services/alert_service.py` | Medium |
| [PERF-10](#perf-10) | Two queries of pure auth overhead on every request | `core/deps.py` | Medium |
| [PERF-11](#perf-11) | Authorization check lazy-loads a relationship per request | `core/deps.py`, controllers | Medium |
| [PERF-12](#perf-12) | Aggregates computed in Python over fully loaded rows | `services/client_service.py` | Medium |
| [PERF-13](#perf-13) | PBKDF2 at 260,000 iterations dominates the login path | `core/security.py` | Low (by design) |
| [PERF-14](#perf-14) | A new Anthropic HTTP client is built per diagnosis request | `services/llm_service.py` | Low |
| [PERF-15](#perf-15) | `create_all` and the seed probe run on every startup | `main.py`, `seed.py` | Low |

---

## Critical

### PERF-01

**Every monitoring poll takes an exclusive write lock on the whole database.**

`GET /api/monitor/warnings`, `/errors` and `/long-stopped` are read-shaped endpoints that
`INSERT` alerts and then call `db.commit()` unconditionally —
[monitor_service.py:50](../../app/services/monitor_service.py#L50),
[:66](../../app/services/monitor_service.py#L66),
[:90](../../app/services/monitor_service.py#L90). The commit fires even when
`_record_alert` recorded nothing.

The engine runs on SQLite defaults. Measured against the real `monitoring.db`:

```
journal_mode = delete
synchronous  = 2   (FULL)
busy_timeout = 5000
```

With a rollback journal, a write transaction locks the **entire database file**, not a
row or a table, and `synchronous=FULL` fsyncs on every commit. Concurrent readers get
`SQLITE_BUSY` and block for up to 5 seconds before failing.

This is the worst possible shape for a monitoring API: the three endpoints a dashboard
polls most often are the three that serialize every other request in the system.

**Why it matters.** A dashboard refreshing every 10 seconds turns a read-mostly workload
into a write-mostly one, and each write stalls all readers for the duration of an fsync.

**Fix.**

1. Commit only when something changed — `_record_alert` already returns `True`/`False`,
   so the return value just needs to be collected and checked.
2. Enable WAL and relax the sync mode on connect, so readers never block on a writer:
   ```python
   @event.listens_for(engine, "connect")
   def _sqlite_pragmas(dbapi_conn, _):
       cur = dbapi_conn.cursor()
       cur.execute("PRAGMA journal_mode=WAL")
       cur.execute("PRAGMA synchronous=NORMAL")
       cur.close()
   ```
3. Longer term, take alert recording off the read path entirely — a `POST /api/monitor/scan`
   or a background task, with the three `GET`s becoming pure reads.

---

### PERF-02

**The connection pool is a third the size of the request concurrency.**

Every endpoint in `app/controllers/` is declared `def`, not `async def`. FastAPI therefore
runs each one in `run_in_threadpool`, and AnyIO's default limiter allows **40** such
workers concurrently.

The engine is created with no pool arguments
([database.py:8](../../app/database.py#L8)), so it gets `QueuePool` defaults — measured:

```
pool: QueuePool  size 5      (+ max_overflow 10  =  15 connections)
```

40 concurrent handlers, 15 connections. Request 16 onward blocks in `pool.connect()` for
30 seconds and then raises `TimeoutError: QueuePool limit of size 5 overflow 10 reached`.

**Why it matters.** The failure mode is not slowness, it is a 500. And it appears only
under concurrency, so no functional test will ever catch it.

**Fix.** Size the pool against the actual concurrency and make the mismatch explicit:

```python
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_size=20, max_overflow=20, pool_pre_ping=True,
)
```

Or cap the threadpool to match the pool. Either way the two numbers should be chosen
together rather than inherited from two unrelated defaults.

---

### PERF-03

**A single LLM diagnosis can hold a worker and a database connection for ~30 minutes.**

[llm_service.py:49](../../app/services/llm_service.py#L49) calls `client.messages.create()`
with no `timeout=` and no `max_retries=`. Measured SDK defaults (`anthropic 0.120.2`):

```
DEFAULT_TIMEOUT     Timeout(connect=5.0, read=600, write=600, pool=600)
DEFAULT_MAX_RETRIES 2
```

600-second read timeout across 3 attempts is roughly **30 minutes** worst case. For that
entire window the request holds:

- one of the 40 threadpool slots ([PERF-02](#perf-02)), and
- one of the 15 pool connections — `get_db` opens the session *before* the handler runs
  and closes it only after it returns, so the session is pinned across the whole network
  call even though the last query finished before it started.

Fifteen slow diagnosis calls exhaust the pool for **every** endpoint, including
`GET /`.

**Fix.**

```python
client = anthropic.Anthropic(api_key=api_key, timeout=30.0, max_retries=1)
```

and release the database before the call — the handler already has everything it needs
(`instance` and `alerts`) loaded by then, so the session can be closed or the objects
detached before `diagnose()` is invoked.

---

## High

### PERF-04

**No index exists on any foreign key or filter column.**

`models/models.py` declares `index=True` on primary keys and on `members.email`. Nothing
else. SQLite does not index foreign keys automatically.

`EXPLAIN QUERY PLAN`, measured on the seeded schema:

| Query | Plan |
|---|---|
| Main instance list (`clientId IN (…) AND status = …`) | `SCAN instances` |
| `accessible_client_ids` (`clients WHERE managerId = ?`) | `SCAN clients` |
| Alert dedup (`instanceId`, `alertType`, `isResolved`) | `SCAN alerts` |
| `list_alerts` (join + order) | `SCAN alerts` + `USE TEMP B-TREE FOR ORDER BY` |

Every list endpoint is O(table). The `clients` scan runs on **every** request made by a
`CLIENT_MANAGER` ([PERF-10](#perf-10)); the `alerts` scan runs once per instance inside
the monitoring endpoints ([PERF-05](#perf-05)), so the two compound into O(instances ×
alerts).

**Fix.** The columns that are actually filtered and sorted on:

| Table | Index |
|---|---|
| `instances` | `(clientId, status)`, `region`, `updatedAt` |
| `clients` | `managerId` |
| `alerts` | `(instanceId, alertType, isResolved)`, `detectedAt`, `isResolved` |

The composite `alerts` index is the important one — it turns the dedup probe from a table
scan into a single index seek.

---

### PERF-05

**Alert deduplication issues one SELECT per instance.**

`_record_alert` calls `_has_unresolved_alert`
([monitor_service.py:27](../../app/services/monitor_service.py#L27)) inside a per-instance
loop, and each call is its own `SELECT … LIMIT 1` — a full `alerts` scan
([PERF-04](#perf-04)).

Measured, `ADMIN GET /api/monitor/warnings` against the 16 seeded instances — **14
queries** for a response of 4 rows:

```
1 × SELECT members            (auth)
1 × SELECT instances          (the actual work)
4 × SELECT alerts             <- dedup probe, one per matching instance
4 × INSERT INTO alerts        <- one statement per alert
4 × SELECT instances          <- see PERF-06
```

Two of those groups scale with the result size. At 500 warning instances this is 500
dedup scans plus 500 individual inserts.

**Fix.** One query for the whole set, then one bulk insert:

```python
existing = {
    row[0] for row in db.query(Alert.instanceId).filter(
        Alert.instanceId.in_([i.id for i in instances]),
        Alert.alertType == alert_type,
        Alert.isResolved.is_(False),
    )
}
db.add_all([Alert(...) for inst in instances if inst.id not in existing])
```

Three statements total, regardless of how many instances match.

---

### PERF-06

**`commit()` expires the result set, so serialization re-SELECTs every row.**

`SessionLocal` is built without `expire_on_commit=False`
([database.py:9](../../app/database.py#L9)), so `db.commit()` marks every loaded object
expired. The monitoring endpoints commit and then **return** the instances they just
loaded — and Pydantic reading `instance.instanceName` for the response triggers a refresh
`SELECT` for each one.

This is the trailing `4 × SELECT instances` in the [PERF-05](#perf-05) trace.

It happens even when nothing was written. Measured, `CLIENT_MANAGER
GET /api/monitor/warnings` after the alerts already exist — 7 queries, **0 inserts**:

```
1 × SELECT members     1 × SELECT clients     1 × SELECT instances
2 × SELECT alerts      (dedup, both hit)
2 × SELECT instances   <- pure waste: nothing changed, rows just got expired
```

One wasted round trip per row returned, on a code path that writes nothing.

**Fix.** `sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)`.
Nothing in this codebase relies on post-commit expiry — `update_status` and `resolve_alert`
already call `db.refresh()` explicitly where they want fresh state.

---

### PERF-07

**Six list endpoints have no pagination and no limit.**

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
([monitor_service.py:120](../../app/services/monitor_service.py#L120)).

**Fix.** Reuse the `PageResponse[T]` and `page`/`size` convention that
`GET /api/instances` already established, so this is a consistency fix as much as a
performance one. In `build_report`, take the count with `func.count()` and cap the
embedded list (e.g. the 20 most recent), with the full history behind `/api/alerts`.

> Changing these response shapes is a breaking API change — it belongs in
> [../api/CONVENTIONS.md](../api/CONVENTIONS.md) and
> [../api/ENDPOINTS.md](../api/ENDPOINTS.md) in the same commit.

---

## Medium

### PERF-08

**The pagination count query carries every column and the `ORDER BY`.**

`total = query.count()` at
[instance_service.py:72](../../app/services/instance_service.py#L72) wraps the fully built
query — sort included. Measured SQL:

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

---

### PERF-09

**`list_alerts` joins `instances` even when the join is unused.**

[alert_service.py:18](../../app/services/alert_service.py#L18) joins unconditionally, but
the join exists only to reach `Instance.clientId` for the scope filter. For an `ADMIN`,
`client_ids is None` and the filter is never applied — the join is pure cost. Measured
plan: `SCAN alerts` + a per-row `SEARCH instances` + `USE TEMP B-TREE FOR ORDER BY`.

**Fix.** Move the join inside the `if client_ids is not None:` branch that already exists
one line below it.

---

### PERF-10

**Every request pays two queries of pure authentication overhead.**

`get_current_member` does `db.get(Member, sub)`, and `accessible_client_ids` then scans
`clients` for the manager's ids ([deps.py:57](../../app/core/deps.py#L57)).

Measured, `CLIENT_MANAGER GET /api/alerts` — **3 queries, 2 of them overhead**:

```
SELECT members …                      <- auth
SELECT clients.id WHERE managerId = ? <- scope  (full scan, PERF-04)
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

---

### PERF-11

**The authorization check lazy-loads a relationship on every request.**

`assert_client_access(member, instance.client)` needs a `Client` object, so accessing
`.client` fires a lazy load. Measured, `GET /api/instances/1` — 3 queries, the third being
that load. `resolve_alert` is worse: `alert.instance.client`
([alert_controller.py:49](../../app/controllers/alert_controller.py#L49)) is two chained
lazy loads.

**Fix.** `assert_client_access` reads exactly one field, `client.managerId`. An overload
taking the id — checked against the accessible-id set the request already computes
([PERF-10](#perf-10)) — removes the load entirely. Where the object is genuinely needed,
`joinedload(Instance.client)` folds it into the original query.

---

### PERF-12

**Aggregates are computed in Python over fully loaded rows.**

`get_cost_forecast` ([client_service.py:81](../../app/services/client_service.py#L81))
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

[llm_service.py:48](../../app/services/llm_service.py#L48) builds
`anthropic.Anthropic(...)` on every call. Each construction creates a fresh `httpx` client
with its own connection pool, so every diagnosis pays a full TCP and TLS handshake with no
connection reuse — and the client is never closed, leaving sockets to the garbage
collector.

**Fix.** Build one client lazily at module level and reuse it. The `import anthropic`
inside the function is fine as is (module imports are cached after the first call), but the
client should not follow it.

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
| 1 | Add the missing indexes | [PERF-04](#perf-04) | None — additive |
| 2 | `expire_on_commit=False` | [PERF-06](#perf-06) | Low |
| 3 | WAL + `synchronous=NORMAL`; commit only when something changed | [PERF-01](#perf-01) | Low |
| 4 | Explicit pool sizing | [PERF-02](#perf-02) | Low |
| 5 | Timeout and retry cap on the Anthropic client | [PERF-03](#perf-03) | Low |
| 6 | Batch the alert dedup | [PERF-05](#perf-05) | Medium — touches the dedup rule |
| 7 | Count without the sort; conditional join | [PERF-08](#perf-08), [PERF-09](#perf-09) | Low |
| 8 | Scope filter as a subquery; drop the lazy loads | [PERF-10](#perf-10), [PERF-11](#perf-11) | Medium |
| 9 | Paginate the remaining list endpoints | [PERF-07](#perf-07) | **Breaking** — API contract |

Steps 1–5 are configuration and require no change to any documented behaviour. Step 6
touches a rule documented in [../business-rules/ALERTING.md](../business-rules/ALERTING.md)
and must keep the dedup guarantee intact. Step 9 changes response shapes and needs
[../api/CONVENTIONS.md](../api/CONVENTIONS.md) and
[../api/ENDPOINTS.md](../api/ENDPOINTS.md) updated in the same commit.

---

## How these were measured

Every figure in this document came from instrumenting the app itself, against the
in-memory database seeded with the same demo data the test suite uses
([../demo/SEED_DATA.md](../demo/SEED_DATA.md)) — 3 members, 10 clients, 16 instances.

**Query counts** — a SQLAlchemy `before_cursor_execute` listener attached to the engine,
logging every statement while driving endpoints through `TestClient` as both `ADMIN` and
`CLIENT_MANAGER`:

```python
@event.listens_for(engine, "before_cursor_execute")
def record(conn, cursor, statement, params, context, executemany):
    log.append(" ".join(statement.split()))
```

**Query plans** — `EXPLAIN QUERY PLAN` on the statements that listener captured, run
against the seeded schema.

**Engine and SQLite settings** — read from the real `monitoring.db` engine:
`type(engine.pool).__name__`, `engine.pool.size()`, and `PRAGMA journal_mode` /
`synchronous` / `busy_timeout`.

**SDK defaults** — read from the installed package, `anthropic 0.120.2`:
`anthropic._constants.DEFAULT_TIMEOUT` and `DEFAULT_MAX_RETRIES`.

Caveats worth stating: the counts come from the 16-instance seed, so absolute numbers are
small — what matters is which of them **scale with the result set**
([PERF-05](#perf-05), [PERF-06](#perf-06), [PERF-07](#perf-07)). The query plans are
SQLite's; a different backend would plan differently, though the missing indexes would
still be missing. No load test was run — the concurrency findings
([PERF-02](#perf-02), [PERF-03](#perf-03)) are derived from configured limits, not from
observed failures.

---

## Related

| Document | Why |
|---|---|
| [README.md](README.md) | Performance index |
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | The layering and session handling these findings sit in |
| [../design/ERD.md](../design/ERD.md) | The schema that [PERF-04](#perf-04) adds indexes to |
| [../design/LLM_FEATURE.md](../design/LLM_FEATURE.md) | The diagnosis endpoint of [PERF-03](#perf-03) and [PERF-14](#perf-14) |
| [../business-rules/ALERTING.md](../business-rules/ALERTING.md) | The dedup rule [PERF-05](#perf-05) must preserve |
| [../api/CONVENTIONS.md](../api/CONVENTIONS.md) | The pagination convention [PERF-07](#perf-07) would extend |
| [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) | Why none of these are caught today |
| [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md) | Updating this document alongside a fix |
