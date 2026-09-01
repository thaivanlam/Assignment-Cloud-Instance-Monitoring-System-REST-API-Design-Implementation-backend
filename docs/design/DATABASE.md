# Database engine and in-memory SQLite

Which database the application opens, how the URL decides the connection pool, how a
request's session behaves, and where the in-memory mode is actually used.

Engine construction lives in [app/database.py](../../app/database.py); the test engine is
built separately in [tests/conftest.py](../../tests/conftest.py).

---

## 1. Where the database URL comes from

| Source | Value | Applies to |
|---|---|---|
| [app/config.py](../../app/config.py) — `Settings.DATABASE_URL` | `sqlite:///./monitoring.db` | The default when nothing overrides it |
| `.env` (and `.env.example`) — `DATABASE_URL` | `sqlite:///./monitoring.db` | Local runs; the committed value matches the default |
| Environment variable `DATABASE_URL` | anything | Deployment |
| [tests/conftest.py](../../tests/conftest.py) — hard-coded `"sqlite://"` | in-memory | The test suite, which never reads `settings.DATABASE_URL` |

Settings are resolved **at import time**, so a change to `.env` takes effect on the next
restart, not on the next request.

---

## 2. What the URL decides

[app/database.py](../../app/database.py) reads the URL twice, for two different decisions:

```python
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

IS_MEMORY_SQLITE = IS_SQLITE and (
    ":memory:" in settings.DATABASE_URL
    or settings.DATABASE_URL.rstrip("/") == "sqlite:"
)
```

- `IS_SQLITE` gates two things: `check_same_thread=False` in `connect_args`, and the
  `_set_sqlite_pragmas` connect hook that puts every connection in WAL mode.
- `IS_MEMORY_SQLITE` gates the pool sizing. `.rstrip("/")` normalises both `sqlite://`
  and `sqlite:///` — the two spellings of "no file" — to `sqlite:`.

The distinction is not stylistic. SQLAlchemy picks a different pool class per URL, and the
two classes take different arguments:

| URL | Pool class | Pool sizing applied |
|---|---|---|
| `sqlite:///./monitoring.db` | `QueuePool` | Yes — `pool_size=20`, `max_overflow=20`, `pool_pre_ping=True` |
| `sqlite:///:memory:` | `SingletonThreadPool` | No |
| `sqlite://` | `SingletonThreadPool` | No |

Verified against SQLAlchemy 2.0.51:

```bash
python -c "from sqlalchemy import create_engine; print(type(create_engine('sqlite://').pool).__name__)"
# SingletonThreadPool
```

Passing the sizing anyway is a hard failure at import, not a warning:

```
TypeError: Invalid argument(s) 'max_overflow' sent to create_engine(), using
configuration SQLiteDialect_pysqlite/SingletonThreadPool/Engine.
```

That `TypeError` is the entire reason `IS_MEMORY_SQLITE` exists. Background on the sizing
itself:
[../performance/PERFORMANCE_BUGS.md § PERF-02](../performance/PERFORMANCE_BUGS.md#perf-02).

---

## 3. The session factory

The engine decides *how* the application connects. `SessionLocal` decides what a request
does with the connection it borrows:

```python
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
)
```

| Argument | Effect |
|---|---|
| `autocommit=False` | A statement does not commit itself; a service commits explicitly or nothing is written |
| `autoflush=False` | A pending change is not flushed by the next query; the flush happens at `commit()` |
| `expire_on_commit=False` | Objects loaded before a `commit()` stay usable after it, instead of being re-fetched on the next attribute read |

The third one is the one worth explaining, because SQLAlchemy's default is the opposite.
On the default, `commit()` marks every object in the session expired, so the *next* read
of any attribute silently issues a `SELECT` to reload the row. That is a sensible default
for a session that outlives its transaction and might be looking at rows another
transaction has since changed. It is the wrong default here: a request opens its own
session, commits at most once, and then serialises rows it loaded moments earlier and
mutated itself. The monitoring scans are the clearest case — they commit the alerts they
recorded and then return the instances they scanned, so Pydantic reading
`instance.instanceName` re-fetched every row.

The cost was one `SELECT` per row returned, on top of the query that had just returned
them. Measured on the seeded database, an `ADMIN` `GET /api/monitor/warnings` first scan:
8 statements for 4 instances, of which 5 were `SELECT`s against `instances` — one query
and four refreshes. It is 4 statements now, and the count no longer grows with the result
set.

What the setting does **not** change: `db.refresh()` still refreshes. `create_instance`,
`update_status`, `create_client` and `resolve_alert` each call it after their commit and
each still issues the same single `SELECT` — on the default they were paying for it
implicitly, and now they ask for it. Background and the full before/after trace:
[../performance/PERFORMANCE_BUGS.md § PERF-06](../performance/PERFORMANCE_BUGS.md#perf-06).

The test fixture builds its own session factory with the same three arguments
([tests/conftest.py](../../tests/conftest.py)), so the suite exercises the same session
semantics the application runs on.

---

## 4. Where in-memory SQLite is used

In exactly one place that runs: **the test suite**. Everything else is a guard or a
comment about it.

| Place | What it is |
|---|---|
| [tests/conftest.py](../../tests/conftest.py) — the `api` fixture | The real use. One in-memory database per test, seeded, injected by overriding `get_db` |
| [app/database.py](../../app/database.py) — `IS_MEMORY_SQLITE` | A guard, so a manually set in-memory `DATABASE_URL` does not raise `TypeError` at import |
| `.env`, `.env.example` — the comment on the `DATABASE_URL` line | Advertises the option |

The application itself never runs on an in-memory database — not locally, not in the
tests, not in deployment. See § 6 for why it cannot.

### The test fixture

```python
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
```

Three choices, each load-bearing:

- **`"sqlite://"`** — a database that exists only in this process's memory. Every test
  starts from an empty schema, so tests may create, mutate and delete freely and may run
  in any order.
- **`poolclass=StaticPool`** — overrides the `SingletonThreadPool` the URL would otherwise
  get. `SingletonThreadPool` keeps *one connection per thread*, and every connection to
  `sqlite://` opens **its own** empty database. `TestClient` runs the handler in a worker
  thread while the test body asserts from the main thread, so the two would see different
  databases. `StaticPool` hands the same single connection to every thread, which is what
  makes `client, db = api` coherent.
- **`check_same_thread=False`** — required as a consequence: the `sqlite3` driver
  otherwise refuses a connection used from a thread other than the one that opened it.

The fixture calls `engine.dispose()` in teardown. `StaticPool` holds its connection open,
and an in-memory database lives exactly as long as its last connection, so disposal is what
actually frees it — without that call every test leaves a live database behind and the
suite slows down as it runs.

What the fixture is used to assert:
[../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md).

---

## 5. What in-memory mode does not get

- **No pool sizing.** `SingletonThreadPool` has no overflow to configure, and the test
  suite needs none — it overrides `get_db` with a single session.
- **No WAL.** Two independent reasons. The `_set_sqlite_pragmas` hook is registered with
  `@event.listens_for(engine, "connect")` against *the application's* engine object, so an
  engine built in `conftest.py` never runs it. And an in-memory database cannot be put in
  WAL anyway — `PRAGMA journal_mode=WAL` returns `memory` and the setting is ignored.
  Neither matters here: WAL exists to stop a writer from locking a file that readers
  share, and there is no file.
- **No persistence.** The database disappears when its last connection closes. Nothing
  written by a test survives that test.
- **No sharing across processes.** Two `uvicorn --workers` processes, or two serverless
  invocations, would each hold a separate empty database.

---

## 6. Do not run the application on an in-memory URL

Setting `DATABASE_URL=sqlite:///:memory:` and starting the API imports cleanly — the guard
in § 2 sees to that — and then fails on the first request that touches a table:

```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: members
```

The mechanism: `lifespan()` creates the schema and seeds it on the main thread, but every
controller is declared `def`, so FastAPI runs it in an AnyIO worker thread.
`SingletonThreadPool` gives that thread a *new* connection, and a new connection to an
in-memory URL is a new, empty database. The schema created at startup sits in a database
no request can reach.

The guard exists so that a URL a developer sets deliberately does not break the import —
it is not an endorsement of running the server that way. For a throwaway application
database, point `DATABASE_URL` at a temporary **file** instead:

```bash
DATABASE_URL=sqlite:///./scratch.db uvicorn app.main:app --reload
```

A file path gets `QueuePool`, the sized pool and WAL, exactly like `monitoring.db`.

---

## 7. Checking any of this yourself

```bash
# Which pool class a URL gets
python -c "from sqlalchemy import create_engine; print(type(create_engine('sqlite:///./monitoring.db').pool).__name__)"

# What the running application decided
python -c "from app.database import IS_SQLITE, IS_MEMORY_SQLITE, engine; print(IS_SQLITE, IS_MEMORY_SQLITE, type(engine.pool).__name__)"

# What a session does on commit
python -c "from app.database import SessionLocal; print(SessionLocal.kw['expire_on_commit'])"

# That an in-memory database refuses WAL
python -c "import sqlite3; print(sqlite3.connect(':memory:').execute('PRAGMA journal_mode=WAL').fetchone())"
```

---

## 8. Related

| Document | Why |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Startup, the SQLite pragmas and the pool sizing in context |
| [ERD.md](ERD.md) | The tables this engine serves |
| [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) | The fixture that owns the in-memory database |
| [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) | PERF-01 (WAL), PERF-02 (pool sizing) and PERF-06 (`expire_on_commit`), with measurements |
