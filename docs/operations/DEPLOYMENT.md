# Deployment

How to launch this API — on a laptop, on a single server, and as a serverless function —
what a healthy start looks like, how to verify it, and how to upgrade or roll it back.

Configuration and secrets are a separate document:
[CONFIGURATION.md](CONFIGURATION.md). When a launch fails, go to
[RUNBOOKS.md](RUNBOOKS.md).

---

## 1. What is being deployed

One ASGI application and one file. There is no separate database server, no cache, no
queue, and no required third-party service.

| Piece | What it is | Notes |
|---|---|---|
| `app.main:app` | The FastAPI application | 19 endpoints plus `GET /` — [../api/ENDPOINTS.md](../api/ENDPOINTS.md) |
| `monitoring.db` | SQLite file, created on first start | Plus `monitoring.db-wal` and `monitoring.db-shm` in WAL mode |
| `.env` | Settings and secrets | Optional — every setting has a working default |
| Anthropic API | Used only by `GET /api/instances/{id}/diagnosis` | Optional — the endpoint falls back to a rule-based answer |

The consequence worth planning around: **the entire state of the system is one SQLite
file next to the process.** Back that file up and you have backed up the deployment; put
the process somewhere the file does not survive and the deployment resets — see § 6.

---

## 2. Prerequisites

| Requirement | Value |
|---|---|
| Python | Verified on **3.14.6**; 3.11+ expected (the code uses `X \| None` annotations) |
| Disk | A writable working directory — SQLite writes the database, its WAL and its shared-memory file there |
| Network | Outbound HTTPS to `api.anthropic.com` **only** if the LLM diagnosis path is wanted |
| OS | Windows, Linux and macOS all supported; the commands below give both shells |

Dependencies are listed in [../../requirements.txt](../../requirements.txt). The versions
this document was verified against: FastAPI 0.141.1, Uvicorn 0.52.0, SQLAlchemy 2.0.51,
Pydantic 2.13.4, PyJWT 2.13.0, Anthropic SDK 0.120.2.

---

## 3. Launch — local development

```bash
# 1 · from the repository root
python -m venv .venv
.venv\Scripts\activate            # Windows   (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

# 2 · optional — every setting has a default that works
copy .env.example .env            # Windows   (Linux/macOS: cp .env.example .env)

# 3 · run
uvicorn app.main:app --reload
```

Swagger UI: <http://127.0.0.1:8000/docs>.

> **Run from the repository root.** `DATABASE_URL` defaults to the *relative* path
> `sqlite:///./monitoring.db`, and `app` must be importable — starting from `tests/` or
> from a parent directory fails
> ([RUNBOOKS.md § R1](RUNBOOKS.md#r1--the-server-will-not-start-modulenotfounderror),
> [§ R3](RUNBOOKS.md#r3--unable-to-open-database-file)).

`--reload` restarts the process on every file save. It is for development only: it costs
a file watcher, and a restart drops in-flight requests.

### What the first start does

The lifespan hook in [../../app/main.py](../../app/main.py) runs three things before the
first request is served:

1. `Base.metadata.create_all` — creates the five tables if they are absent.
2. Every declared index, created individually with `checkfirst=True` — `create_all` skips
   a table that already exists, indexes included, so a database file made before an index
   was declared would never get it. There is no migration step
   ([../design/ERD.md](../design/ERD.md)).
3. `seed()` — inserts the demo members, clients, instances and cost snapshots. It is
   idempotent: it returns immediately if any member row already exists
   ([../demo/SEED_DATA.md](../demo/SEED_DATA.md)).

A healthy start logs this and nothing else:

```
INFO:     Started server process [13096]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

On a serverless platform all three steps run again on **every cold start** —
[../performance/PERFORMANCE_BUGS.md § PERF-15](../performance/PERFORMANCE_BUGS.md#perf-15).

---

## 4. Verify a deployment

Four calls, in order. Run them against any environment; only the base URL changes.

```bash
BASE=http://127.0.0.1:8000

# 1 · process is up and serving
curl -s $BASE/
# {"status":"ok","service":"TechValley Cloud Instance Monitoring System","docs":"/docs"}

# 2 · the OpenAPI UI renders
curl -s -o /dev/null -w "%{http_code}\n" $BASE/docs      # 200

# 3 · the database is seeded and auth works
curl -s -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@techvalley.vn","password":"admin123!"}'
# {"accessToken":"eyJhbGciOi...","tokenType":"bearer", ...}

# 4 · an authorised read returns data
curl -s "$BASE/api/instances?size=1" -H "Authorization: Bearer <accessToken>"
```

Step 1 proves the process; step 3 proves the *database* — a server whose SQLite file is
missing or empty still answers step 1 and fails step 3
([RUNBOOKS.md § R7](RUNBOOKS.md#r7--the-demo-credentials-are-rejected)).

To check the LLM path as well, call the diagnosis endpoint on an `ERROR` instance and read
the `source` field: `llm` means the provider answered, `rule-based` means it did not
([CONFIGURATION.md § 4](CONFIGURATION.md#4-anthropic_api_key),
[../design/LLM_FEATURE.md](../design/LLM_FEATURE.md)).

The figures every one of these responses should return are in
[../demo/SEED_DATA.md](../demo/SEED_DATA.md), and the same values are asserted by the 104
tests ([../testing/RUNNING_TESTS.md](../testing/RUNNING_TESTS.md)).

---

## 5. Launch — a single server

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

| Flag | Why |
|---|---|
| no `--reload` | The reloader is a development tool; it restarts on file changes and drops in-flight requests |
| `--host 0.0.0.0` | The default `127.0.0.1` accepts only local connections |
| `--proxy-headers` | Behind nginx/Caddy, makes the app read `X-Forwarded-*`; add `--forwarded-allow-ips` with the proxy's address |
| `--workers N` | **Leave it at 1 for this deployment** — see below |

Set `SECRET_KEY` before anything public reaches the process. The default is the literal
placeholder `change-me-to-a-long-random-string`, and anyone who knows it can mint an
`ADMIN` token — [CONFIGURATION.md § 3](CONFIGURATION.md#3-secret_key).

**On `--workers`.** Multiple worker processes share the one SQLite file. WAL mode (set on
every connection by [../../app/database.py](../../app/database.py)) does allow concurrent
readers across processes, and the seed is idempotent, so each worker's startup is safe.
But writes still serialise across the whole file, and the pool sizing was measured for a
single process serving 40 concurrent requests
([../performance/PERFORMANCE_BUGS.md § PERF-02](../performance/PERFORMANCE_BUGS.md#perf-02)).
One worker is the configuration this project has been measured in; more workers is a
change to make deliberately, with `DATABASE_URL` pointed at a real database server first
([../design/DATABASE.md](../design/DATABASE.md)).

### Keeping it running

Any supervisor works — the process must simply be restarted when it exits, and started in
the repository root. A systemd unit:

```ini
[Unit]
Description=TechValley Cloud Instance Monitoring API
After=network.target

[Service]
Type=simple
User=techvalley
WorkingDirectory=/srv/techvalley-backend
EnvironmentFile=/srv/techvalley-backend/.env
ExecStart=/srv/techvalley-backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`WorkingDirectory` is load-bearing: `DATABASE_URL` is a relative path, so a unit started
elsewhere creates a *second, empty* database and the demo logins stop working.

On Windows the equivalent is a service wrapper (NSSM, WinSW) with the same working
directory, or Task Scheduler with *Start in* set to the repository root.

Logs go to stdout and stderr — `journalctl -u techvalley -f` under systemd. The
application writes no log file of its own; see
[RUNBOOKS.md § Reading the logs](RUNBOOKS.md#reading-the-logs).

---

## 6. Launch — serverless (Vercel)

[../../vercel.json](../../vercel.json) builds `app/main.py` with `@vercel/python` and
rewrites every route to it:

```bash
npm i -g vercel
vercel                                      # preview deployment
vercel --prod                               # production
vercel env add SECRET_KEY production        # repeat per secret, then redeploy
```

Environment variables set in the Vercel dashboard or by `vercel env add` reach the app the
way any environment variable does, and take priority over `.env`
([CONFIGURATION.md § 1](CONFIGURATION.md#1-where-settings-come-from)).

**What does not work there, and why.** A serverless function gets an ephemeral filesystem
that is read-only apart from `/tmp`. Two consequences follow, both properties of the
platform rather than defects in this application:

- With the default `DATABASE_URL`, startup tries to create `./monitoring.db` in a
  read-only directory and fails with `unable to open database file`
  ([RUNBOOKS.md § R3](RUNBOOKS.md#r3--unable-to-open-database-file)). Pointing
  `DATABASE_URL` at `sqlite:////tmp/monitoring.db` gets past it.
- Even then, **nothing written survives a cold start**: each cold start rebuilds the
  schema and re-seeds, so a resolved alert reappears and a created client disappears
  ([../performance/PERFORMANCE_BUGS.md § PERF-15](../performance/PERFORMANCE_BUGS.md#perf-15),
  [RUNBOOKS.md § R12](RUNBOOKS.md#r12--data-resets-or-resolved-alerts-come-back)).

That makes the serverless target suitable for a **demo of the API surface**, not for
anything that must remember what it was told. Anything real needs `DATABASE_URL` pointing
at a managed database, that driver added to `requirements.txt`, and schema creation moved
out of the startup hook into a migration step.

---

## 7. Upgrade a running deployment

```bash
git pull
.venv/bin/pip install -r requirements.txt   # only when requirements.txt changed
pytest -q                                   # 104 passed — needs requirements-dev.txt
sudo systemctl restart techvalley
curl -s http://127.0.0.1:8000/              # then the rest of § 4
```

There is no migration step and no schema versioning. New tables and new indexes are
created by the startup hook (§ 3); a **changed or removed** column is not — that case has
to be applied by hand, or rebuilt from a clean database (§ 9).

Read [../changelog/CHANGELOG.md](../changelog/CHANGELOG.md) before an upgrade: it records
every change a reader would notice, including the ones that move a documented number.

---

## 8. Roll back

```bash
git log --oneline -5                 # find the last good commit
git checkout <good-commit>           # or: git revert <bad-commit>
.venv/bin/pip install -r requirements.txt
sudo systemctl restart techvalley
curl -s http://127.0.0.1:8000/
```

Rolling the **code** back is quick and safe. Rolling the **data** back is not automatic:
an index or table the newer version added stays in the file, which is harmless because the
older code ignores it. If the newer version wrote rows the older code cannot read, restore
the database from a backup (§ 9) instead.

---

## 9. Back up, restore, and reset

Do not copy `monitoring.db` with `cp` while the server runs — in WAL mode the newest
commits live in `monitoring.db-wal`, and a copy without it is a torn snapshot. Use
SQLite's own backup, which is consistent against a live database:

```bash
python -c "import sqlite3,sys; sqlite3.connect('monitoring.db').execute('VACUUM INTO ?', (sys.argv[1],))" \
  backups/monitoring-2026-09-01.db
```

Restore is a stop, a copy and a start:

```bash
sudo systemctl stop techvalley
rm -f monitoring.db monitoring.db-wal monitoring.db-shm
cp backups/monitoring-2026-09-01.db monitoring.db
sudo systemctl start techvalley
```

To reset to the seeded demo state instead, delete the three files and start — the schema
is recreated and the seed runs again
([RUNBOOKS.md § R14](RUNBOOKS.md#r14--reset-to-a-clean-seeded-database)).

---

## 10. Related

| Document | Why |
|---|---|
| [CONFIGURATION.md](CONFIGURATION.md) | Every setting, how to generate the keys, and what a rotation breaks |
| [RUNBOOKS.md](RUNBOOKS.md) | The failure a launch just hit, and what to do about it |
| [../design/DATABASE.md](../design/DATABASE.md) | Which pool each `DATABASE_URL` gets, and why in-memory is not a deployment mode |
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | The layering and the configuration table this document deploys |
| [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) | The measured limits behind the worker and pool advice |
| [../testing/RUNNING_TESTS.md](../testing/RUNNING_TESTS.md) | The suite to run before restarting a deployment |
| [../demo/SEED_DATA.md](../demo/SEED_DATA.md) | The figures a verified deployment returns |
| [../changelog/CHANGELOG.md](../changelog/CHANGELOG.md) | What an upgrade is about to change |
