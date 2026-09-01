# Operations

Running this API in an environment other than a laptop — launching it, giving it its keys,
and fixing it when it stops working. Written for whoever is on call, including someone who
has never read the source.

| Document | Contents |
|---|---|
| [DEPLOYMENT.md](DEPLOYMENT.md) | Launching locally, on a single server and on Vercel; what a healthy start logs; the four calls that verify a deployment; upgrade, rollback, backup and reset |
| [CONFIGURATION.md](CONFIGURATION.md) | Every setting and where it comes from; generating `SECRET_KEY`; the Anthropic key and its fallback; what `DATABASE_URL` selects; reading back the effective configuration |
| [RUNBOOKS.md](RUNBOOKS.md) | Fifteen incident runbooks — symptom, cause, fix, verification — plus a 60-second triage, how to read the logs, and what to collect before escalating |

## The short version

```bash
pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn app.main:app --host 0.0.0.0 --port 8000       # no --reload outside development
curl -s http://127.0.0.1:8000/                        # {"status":"ok",...}
```

Three facts explain most of what an operator needs to know:

- **The whole state is one SQLite file.** `monitoring.db` and its `-wal` / `-shm`
  companions are created next to the process on first start, from a relative path — so the
  working directory decides which database the server opens, and a deployment where that
  file does not persist resets to the demo data on every restart.
- **Everything has a working default, including the JWT key** — and that default is
  published in this repository. `SECRET_KEY` is the one setting that must be changed before
  anything public reaches the process.
- **No external service is required.** The Anthropic key is optional: with none set, or a
  bad one, `GET /api/instances/{id}/diagnosis` returns a rule-based answer instead of
  failing. Nothing else calls out.

Startup creates the schema, adds any missing index, and seeds the demo data if the database
has no members. There is no migration step, so a changed column is the one upgrade that
needs manual work.

## Related

| Document | Why |
|---|---|
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | The application being deployed, and its configuration from the design side |
| [../design/DATABASE.md](../design/DATABASE.md) | Which engine and pool each `DATABASE_URL` produces |
| [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) | The measured limits behind the pool, worker and timeout advice |
| [../demo/README.md](../demo/README.md) | The seeded accounts and figures a verified deployment returns |
| [../testing/RUNNING_TESTS.md](../testing/RUNNING_TESTS.md) | The suite to run before restarting a deployment |
| [../api/ERRORS.md](../api/ERRORS.md) | Which status codes are deliberate, so a `500` stands out in the logs |
| [../changelog/CHANGELOG.md](../changelog/CHANGELOG.md) | What an upgrade is about to change |
