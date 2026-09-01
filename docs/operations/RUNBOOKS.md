# Incident runbooks

What to do when the API will not start, stops answering, or answers wrongly. Each runbook
is one symptom: what it looks like, what causes it, how to fix it, and how to confirm the
fix.

Written for whoever is on call, including someone who has never read this codebase. Where
a fix depends on a setting, the setting is explained in
[CONFIGURATION.md](CONFIGURATION.md); where it depends on how the process was launched,
see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## First 60 seconds

Four questions, in this order. Most incidents are identified before the fourth.

```bash
BASE=http://127.0.0.1:8000

curl -s $BASE/                          # 1 · is the process serving?
journalctl -u techvalley -n 50          # 2 · what did it log? (or the terminal it runs in)
ls -l monitoring.db*                    # 3 · does the database file exist, and is it growing?
git log --oneline -3                    # 4 · what changed recently?
```

| Answer to #1 | Go to |
|---|---|
| Connection refused / nothing listening | [R1](#r1--the-server-will-not-start-modulenotfounderror)–[R5](#r5--modulenotfounderror-no-module-named-psycopg2) — it never started, or it crashed at startup |
| `{"status":"ok",...}` but calls fail | [R6](#r6--every-request-returns-401-after-a-restart)–[R9](#r9--500s-under-load-queuepool-timeout) |
| Answers, but slowly | [R9](#r9--500s-under-load-queuepool-timeout), [R10](#r10--the-diagnosis-endpoint-is-slow), [R13](#r13--list-endpoints-are-slow) |
| Answers, but with the wrong data | [R7](#r7--the-demo-credentials-are-rejected), [R12](#r12--data-resets-or-resolved-alerts-come-back) |

---

## Symptom index

| Symptom | Runbook |
|---|---|
| `ModuleNotFoundError: No module named 'app'` / `'fastapi'` | [R1](#r1--the-server-will-not-start-modulenotfounderror) |
| `[Errno 10048]` / `Address already in use` | [R2](#r2--the-port-is-already-in-use) |
| `sqlite3.OperationalError: unable to open database file` | [R3](#r3--unable-to-open-database-file) |
| `TypeError: Invalid argument(s) 'max_overflow'` | [R4](#r4--typeerror-invalid-arguments-max_overflow) |
| `ModuleNotFoundError: No module named 'psycopg2'` | [R5](#r5--modulenotfounderror-no-module-named-psycopg2) |
| Everything answers `401` after a restart | [R6](#r6--every-request-returns-401-after-a-restart) |
| The demo login is rejected | [R7](#r7--the-demo-credentials-are-rejected) |
| `sqlite3.OperationalError: database is locked` | [R8](#r8--database-is-locked) |
| `500`s under load, `QueuePool limit … reached` | [R9](#r9--500s-under-load-queuepool-timeout) |
| A diagnosis takes half a minute or more | [R10](#r10--the-diagnosis-endpoint-is-slow) |
| `"source":"rule-based"` with a key configured | [R11](#r11--diagnosis-answers-rule-based-when-a-key-is-configured) |
| Created data disappears; resolved alerts return | [R12](#r12--data-resets-or-resolved-alerts-come-back) |
| List endpoints got slow as data grew | [R13](#r13--list-endpoints-are-slow) |
| Need a clean database | [R14](#r14--reset-to-a-clean-seeded-database) |
| `InsecureKeyLengthWarning` on startup | [R15](#r15--insecurekeylengthwarning-on-startup) |

---

## R1 · The server will not start (ModuleNotFoundError)

**Symptom**

```
ModuleNotFoundError: No module named 'app'
ModuleNotFoundError: No module named 'fastapi'
```

**Cause.** The first is the wrong working directory — `uvicorn app.main:app` imports `app`
as a package relative to where the command runs. The second is a virtualenv that is not
active, or dependencies that were never installed.

**Fix**

```bash
cd /srv/techvalley-backend          # the repository root — the folder containing app/
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app
```

Under a supervisor, the same mistake appears as a `WorkingDirectory` (systemd) or *Start
in* (Windows) pointing somewhere else — [DEPLOYMENT.md § 5](DEPLOYMENT.md#5-launch--a-single-server).

**Verify.** `curl -s http://127.0.0.1:8000/` returns `{"status":"ok",...}`.

---

## R2 · The port is already in use

**Symptom**

```
ERROR:    [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8011):
          [winerror 10048] only one usage of each socket address ... is normally permitted
```

On Linux and macOS the same failure reads `[Errno 98] Address already in use`. Note that
uvicorn logs `Application startup complete` *before* it binds — a run that seeded the
database and then died on this error did start the application, so seeing a startup line
does not mean the port was free.

**Cause.** An earlier server is still running — very often a `--reload` process from an
earlier session that lost its terminal.

**Fix — find and stop it, or move.**

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <pid> /F

# Linux / macOS
ss -ltnp 'sport = :8000'          # or: lsof -i :8000
kill <pid>

# or simply choose another port
uvicorn app.main:app --port 8001
```

**Verify.** The startup log ends with `Uvicorn running on http://…` and `curl` on that
port answers.

---

## R3 · `unable to open database file`

**Symptom**

```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
```

Raised during startup, from `create_all` — the process exits before it serves anything.

**Cause.** SQLite could not create or open the file at `DATABASE_URL`. In order of
likelihood:

| Cause | Check |
|---|---|
| The directory in the path does not exist — SQLite creates the *file*, never the folder | `ls -d $(dirname <path>)` |
| The working directory is not the repository root, and the relative path resolves somewhere unwritable | `pwd` |
| The process user cannot write the directory | `sudo -u techvalley touch <dir>/probe` |
| A read-only filesystem — the normal case on serverless | [DEPLOYMENT.md § 6](DEPLOYMENT.md#6-launch--serverless-vercel) |

**Fix.** Create the directory and grant the process user write access, or point
`DATABASE_URL` at a writable absolute path (`sqlite:////srv/data/monitoring.db` — four
slashes). On a serverless platform the only writable location is `/tmp`:
`DATABASE_URL=sqlite:////tmp/monitoring.db`, with the ephemerality caveat in
[R12](#r12--data-resets-or-resolved-alerts-come-back).

SQLite needs to write **three** files beside the database — `.db`, `.db-wal`, `.db-shm` —
so a writable file in a read-only directory is still a failure.

**Verify.** Restart; `ls -l monitoring.db*` shows all three, and the login in
[DEPLOYMENT.md § 4](DEPLOYMENT.md#4-verify-a-deployment) succeeds.

---

## R4 · `TypeError: Invalid argument(s) 'max_overflow'`

**Symptom**

```
TypeError: Invalid argument(s) 'max_overflow' sent to create_engine(), using
configuration SQLiteDialect_pysqlite/SingletonThreadPool/Engine.
```

A hard failure at *import*, before the application object exists.

**Cause.** `DATABASE_URL` names an in-memory SQLite database in a spelling the guard in
[../../app/database.py](../../app/database.py) does not recognise. In-memory URLs get a
`SingletonThreadPool`, which accepts none of the pool sizing arguments.

**Fix.** Use a file URL. In-memory SQLite is a test-suite fixture, not a deployment mode —
each connection would get its own empty database. The recognised spellings and the reason
for the guard are in [../design/DATABASE.md § 2](../design/DATABASE.md#2-what-the-url-decides).

**Verify.**

```bash
python -c "from app.database import engine; print(type(engine.pool).__name__)"   # QueuePool
```

---

## R5 · `ModuleNotFoundError: No module named 'psycopg2'`

**Symptom.** Import fails with a missing driver — `psycopg2`, `pymysql`, `asyncpg` or
similar — traced through `sqlalchemy/dialects/…/import_dbapi`.

**Cause.** `DATABASE_URL` points at a database whose driver is not installed.
[../../requirements.txt](../../requirements.txt) ships no database driver at all; SQLite
comes with Python.

**Fix.** Either restore the SQLite URL, or install the driver and add it to
`requirements.txt` so the next deployment has it. Moving off SQLite deliberately also
means deciding where the schema comes from: creation still happens in the startup hook,
and there is no migration tool ([DEPLOYMENT.md § 7](DEPLOYMENT.md#7-upgrade-a-running-deployment)).

**Verify.** The import check in [R4](#r4--typeerror-invalid-arguments-max_overflow) prints
a pool name instead of raising.

---

## R6 · Every request returns 401 after a restart

**Symptom.** Health is fine, login works, but tokens issued *before* the restart are
rejected — every call answers `401`.

**Cause.** `SECRET_KEY` changed. A token is only valid for a process holding the key that
signed it. The usual triggers: a deployment that finally set a real key, a generated key
that is regenerated on each boot, or two processes behind a load balancer with different
values.

**Fix.** Set one fixed `SECRET_KEY` for the environment and keep it identical across every
process ([CONFIGURATION.md § 3](CONFIGURATION.md#3-secret_key)). Clients then log in once
more; there is no refresh token, so a rotation is always a forced re-login.

If the key did *not* change, the token has simply expired — the default lifetime is 120
minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`).

**Verify.** Log in again, call `GET /api/instances?size=1` with the new token, and restart
the service once more: the same token must still work afterwards.

---

## R7 · The demo credentials are rejected

**Symptom.** `POST /api/auth/login` with `admin@techvalley.vn` / `admin123!` returns
`401`, while `GET /` is healthy.

**Cause.** The process is looking at a database that is not the seeded one, or at one that
was seeded differently. The seed is idempotent by a single check — *if any member row
exists, it does nothing* — so a database containing real members is never re-seeded.

**Fix**

```bash
python -c "
from app.database import SessionLocal
from app.models import Member
with SessionLocal() as db:
    print([(m.id, m.email, m.role.value) for m in db.query(Member).all()])
"
```

- Empty list → the schema exists but the seed never ran; restart the server from the
  repository root and watch the startup log.
- Different emails → this is a real database, not the demo one. The demo passwords do not
  apply; use the accounts it holds.
- The right emails, wrong password → the password was changed after seeding. Reset with
  [R14](#r14--reset-to-a-clean-seeded-database), which discards all data.

Run the check with the same working directory and environment as the server — otherwise it
opens a different file and reports the wrong answer. The seeded accounts are listed in
[../demo/ACCOUNTS.md](../demo/ACCOUNTS.md).

**Verify.** The login returns an `accessToken`.

---

## R8 · `database is locked`

**Symptom.** Intermittent `500`s, with `sqlite3.OperationalError: database is locked` in
the log — typically on writes: instance creation, status change, alert resolution, or a
monitoring scan recording alerts.

**Cause.** Another connection is holding a write lock for longer than SQLite's busy
timeout. Since the WAL change ([PERF-01](../performance/PERFORMANCE_BUGS.md#perf-01)),
readers no longer block writers, so on a healthy single-process deployment this should be
rare. The realistic causes now are: the database on a network filesystem (NFS, SMB, a
synced folder), where WAL's shared-memory file cannot work correctly; several processes
writing the same file (`--workers > 1`, or a second server left running); or an external
tool holding a transaction open — an interactive `sqlite3` session, a database browser.

**Fix**

```bash
python -c "import sqlite3; print(sqlite3.connect('monitoring.db').execute('PRAGMA journal_mode').fetchone()[0])"
# expected: wal
```

- Not `wal` → the file is being opened by something that reset the mode, or it lives on a
  filesystem that cannot support it. Move it to local disk.
- Close database browsers and stray `sqlite3` sessions.
- Confirm only one server process holds the file (`ss -ltnp`, `netstat -ano`), and keep
  `--workers` at 1 ([DEPLOYMENT.md § 5](DEPLOYMENT.md#5-launch--a-single-server)).

**Verify.** Run a write — resolve an alert, or `PATCH` an instance status — and repeat it
under a monitoring poll; neither should error.

---

## R9 · 500s under load (QueuePool timeout)

**Symptom.** Under concurrency, a share of requests hang for ~30 seconds and then fail
with `500`; the log shows `TimeoutError: QueuePool limit of size 20 overflow 20 reached`.

**Cause.** Every endpoint is synchronous, so FastAPI runs it in AnyIO's threadpool (40
workers by default), and `get_db` holds one connection for the whole request. The pool is
sized to exactly that: 20 + 20 = 40 connections
([PERF-02](../performance/PERFORMANCE_BUGS.md#perf-02)). Exhausting it means either more
than 40 requests genuinely in flight, or requests holding connections far longer than they
should.

**Fix**

1. Look for a slow holder first — a diagnosis call is the usual suspect
   ([R10](#r10--the-diagnosis-endpoint-is-slow)), followed by an unpaginated list endpoint
   ([PERF-07](../performance/PERFORMANCE_BUGS.md#perf-07)).
2. If the load is real, raise the ceiling at both ends together — they must stay equal:
   `MAX_CONCURRENT_REQUESTS` in [../../app/database.py](../../app/database.py) and the
   threadpool limit. Raising the pool alone only moves the queue.
3. Beyond that, SQLite is the wrong store for the load — move `DATABASE_URL` to a database
   server ([R5](#r5--modulenotfounderror-no-module-named-psycopg2) covers the driver).

Changing the pool sizing is a code change with a document attached
([../design/DATABASE.md](../design/DATABASE.md) and
[../design/ARCHITECTURE.md](../design/ARCHITECTURE.md), same commit).

**Verify.** Re-run the load; no `TimeoutError` in the log and no `500`s.

---

## R10 · The diagnosis endpoint is slow

**Symptom.** `GET /api/instances/{id}/diagnosis` takes tens of seconds. Everything else is
normal.

**Cause.** The call to the provider is bounded at 30 seconds with one retry — a 60-second
worst case — after which the rule-based answer is returned
([PERF-03](../performance/PERFORMANCE_BUGS.md#perf-03)). A slow or unreachable provider
therefore shows up as a slow endpoint, never as an error. The request holds a threadpool
worker while it waits, but **not** a database connection: the handler releases its session
before calling out.

**Fix.** If the provider is degraded and a fast answer matters more than a good one, unset
`ANTHROPIC_API_KEY` and restart: the endpoint answers instantly, from the rule-based path,
and every other endpoint is unaffected. Restore the key afterwards.

**Verify.**

```bash
curl -s -o /dev/null -w "%{time_total}s\n" "$BASE/api/instances/11/diagnosis" -H "Authorization: Bearer <token>"
```

---

## R11 · Diagnosis answers `rule-based` when a key is configured

**Symptom.** The response body carries `"source":"rule-based"` although
`ANTHROPIC_API_KEY` is set. The endpoint is *working as designed* — this is the fallback,
not an outage.

**Cause.** The log line names it exactly. With an invalid key, for example:

```
WARNING:app.services.llm_service:LLM diagnosis unavailable, using rule-based fallback:
Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error',
'message': 'API key is invalid.'}, 'request_id': None}
```

| What the warning says | Fix |
|---|---|
| `401 … authentication_error` | Wrong, revoked or truncated key — reissue it |
| `429` / `529` | Rate limited or overloaded — retry later; nothing to fix here |
| `Connection error` / a timeout | No outbound HTTPS to `api.anthropic.com` — check egress rules and any proxy |
| `No module named 'anthropic'` | Dependencies incomplete — `pip install -r requirements.txt` |
| No warning at all | The key never reached the process — [CONFIGURATION.md § 7](CONFIGURATION.md#7-read-back-the-effective-configuration) |

Remember that settings are read at import time: a key added to `.env` after the server
started is not in use until it restarts.

**Verify.** Call the endpoint again and check `"source":"llm"`.

---

## R12 · Data resets, or resolved alerts come back

**Symptom.** A client created through the API is gone; an alert marked resolved is
unresolved again; the totals are back to the seeded figures.

**Two different causes — tell them apart first.**

1. **The database file did not survive.** This is the normal behaviour on a serverless
   deployment: every cold start recreates the schema and re-seeds
   ([PERF-15](../performance/PERFORMANCE_BUGS.md#perf-15)). It also happens on a
   container without a mounted volume, or when the process is restarted in a different
   working directory and creates a second file. Check `ls -l monitoring.db` — a file whose
   modification time is the last restart, holding exactly the seeded row counts, is this
   case. Fix: persist the file (a volume, an absolute `DATABASE_URL` on durable storage)
   or move to a database server. There is no way to make a serverless filesystem durable.
2. **A monitoring scan raised the alert again.** This is the documented rule, not a bug:
   `GET /api/monitor/warnings`, `/errors` and `/long-stopped` record alerts as they scan,
   and the dedup guard only suppresses a *new* alert while an unresolved one of the same
   type exists. Resolve the alert while the instance is still at 91% CPU and the next scan
   legitimately raises a fresh one — [../business-rules/ALERTING.md](../business-rules/ALERTING.md).
   Fix the instance, not the alert.

**Verify.** For (1): create a client, restart the service, and confirm it is still there.

---

## R13 · List endpoints are slow

**Symptom.** `GET /api/instances` and the client endpoints degrade as the data grows,
while writes stay fast.

**Cause.** Most likely the indexes are missing. SQLite creates none for foreign keys, and
`create_all` skips existing tables — including their indexes — so a database file created
before [PERF-04](../performance/PERFORMANCE_BUGS.md#perf-04) landed would have kept
full table scans. The startup hook now creates each index individually with
`checkfirst=True`, which repairs exactly this case on restart.

**Fix**

```bash
python -c "
import sqlite3
print([r[0] for r in sqlite3.connect('monitoring.db').execute(
    \"SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'\")])
"
```

Expect `ix_clients_managerId`, `ix_instances_clientId_status`, `ix_instances_region`,
`ix_instances_updatedAt`, `ix_alerts_instanceId_alertType_isResolved` and
`ix_alerts_detectedAt` alongside the primary-key indexes. Any missing → restart the
server, which creates them.

If they are all present, the remaining candidates are the open findings — the unbounded
list endpoints ([PERF-07](../performance/PERFORMANCE_BUGS.md#perf-07)) and the per-row
re-`SELECT` ([PERF-06](../performance/PERFORMANCE_BUGS.md#perf-06)) — measured and ranked
in [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md).

**Verify.** Time the same call before and after the restart.

---

## R14 · Reset to a clean, seeded database

**When.** A demo needs the documented figures back, or a database is corrupt beyond
repair. **This discards every change made through the API.** Back up first if any of it
matters ([DEPLOYMENT.md § 9](DEPLOYMENT.md#9-back-up-restore-and-reset)).

```bash
sudo systemctl stop techvalley                       # or Ctrl+C in the terminal
rm -f monitoring.db monitoring.db-wal monitoring.db-shm
sudo systemctl start techvalley
```

All three files must go: deleting only `monitoring.db` leaves a WAL that SQLite may treat
as belonging to the new file.

**Verify.** Log in as `admin@techvalley.vn`, then check the seeded totals — 10 clients, 15
instances, `$2,100` monthly cost ([../demo/SEED_DATA.md](../demo/SEED_DATA.md)).

Before deciding a file is corrupt, ask SQLite:

```bash
python -c "import sqlite3; print(sqlite3.connect('monitoring.db').execute('PRAGMA integrity_check').fetchone()[0])"
# expected: ok
```

---

## R15 · `InsecureKeyLengthWarning` on startup

**Symptom.** `InsecureKeyLengthWarning: The HMAC key is 16 bytes long`, logged by PyJWT.

**Cause.** `SECRET_KEY` is shorter than the 32 bytes recommended for HS256. The
application works; the signature is simply weaker than it should be.

**Fix.** Generate a longer key and restart — note that this invalidates existing tokens
([R6](#r6--every-request-returns-401-after-a-restart)):

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

**Verify.** The warning is gone from the startup log.

---

## Reading the logs

The application logs to stdout and stderr through uvicorn's configuration and writes no
file of its own. Under systemd: `journalctl -u techvalley -f`; in a container:
`docker logs -f <name>`; in a terminal, the terminal.

| Line | Meaning |
|---|---|
| `INFO: Application startup complete.` | Tables, indexes and seed are done — but the port is bound *after* this ([R2](#r2--the-port-is-already-in-use)) |
| `INFO: 127.0.0.1:xxxxx - "GET /api/instances HTTP/1.1" 200 OK` | Normal access log, one line per request |
| `WARNING:app.services.llm_service:LLM diagnosis unavailable…` | The fallback answered ([R11](#r11--diagnosis-answers-rule-based-when-a-key-is-configured)) |
| `WARNING:app.services.llm_service:LLM diagnosis hit the max_tokens cap` | The answer may be truncated; the response is still returned |
| `sqlalchemy.exc.*` in a traceback | Database-level failure — [R3](#r3--unable-to-open-database-file), [R8](#r8--database-is-locked), [R9](#r9--500s-under-load-queuepool-timeout) |

`uvicorn --log-level debug` adds detail for a reproduction. Two things worth knowing when
reading a `500`: the four domain exceptions (`404`, `403`, `409`, `400`) are handled and
never appear as tracebacks ([../api/ERRORS.md](../api/ERRORS.md)), so *any* traceback is
unexpected; and no request id is logged, so correlate by timestamp and path.

---

## Collect this before escalating

```bash
git rev-parse --short HEAD                 # the exact code running
python -V                                  # interpreter
pip freeze | grep -Ei "fastapi|uvicorn|sqlalchemy|pydantic|pyjwt|anthropic"
curl -s http://127.0.0.1:8000/             # health
ls -l monitoring.db*                       # database presence and size
journalctl -u techvalley -n 200            # the log around the failure
```

Plus the effective configuration with the secrets redacted
([CONFIGURATION.md § 7](CONFIGURATION.md#7-read-back-the-effective-configuration)) — never
the values themselves.

---

## Related

| Document | Why |
|---|---|
| [DEPLOYMENT.md](DEPLOYMENT.md) | How the process should have been launched, and how to restart or roll it back |
| [CONFIGURATION.md](CONFIGURATION.md) | The settings these runbooks change |
| [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) | The measured findings behind R9, R10, R12 and R13 |
| [../design/DATABASE.md](../design/DATABASE.md) | Engine, pool and WAL — the mechanics behind R4, R8 and R9 |
| [../api/ERRORS.md](../api/ERRORS.md) | Which status codes are deliberate, so a `500` stands out |
| [../business-rules/ALERTING.md](../business-rules/ALERTING.md) | Why a resolved alert can legitimately return (R12) |
| [../demo/SEED_DATA.md](../demo/SEED_DATA.md) | The figures a healthy, freshly seeded deployment returns |
| [../testing/RUNNING_TESTS.md](../testing/RUNNING_TESTS.md) | Confirming a fix did not break behaviour |
