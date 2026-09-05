# CLAUDE.md

## Project

TechValley cloud instance monitoring REST API — FastAPI + SQLAlchemy (SQLite),
Pydantic v2, PyJWT auth, Anthropic SDK for the LLM diagnosis endpoint.

MVC layout under `app/`:

| Dir | Role |
|---|---|
| `models/` | SQLAlchemy 2.0 ORM entities |
| `schemas/` | Pydantic v2 request/response DTOs |
| `controllers/` | APIRouter endpoints |
| `services/` | Business logic (monitoring, alerts, cost, SLA, LLM) |
| `core/` | JWT security, auth dependencies, domain exceptions |

```bash
uvicorn app.main:app --reload   # run (Swagger at /docs)
pytest -q                       # tests — 127 functional tests, no API key needed
```

`monitoring.db` is created and seeded automatically on startup by `app/seed.py`.

The test suite drives the API over HTTP against a per-test in-memory database seeded with
the same demo data, so its expected values are exact. What it covers:
[docs/testing/FUNCTIONAL_TESTS.md](docs/testing/FUNCTIONAL_TESTS.md); how to run it:
[docs/testing/RUNNING_TESTS.md](docs/testing/RUNNING_TESTS.md).

## Documentation rules

These apply to every change in this repository, for every contributor.

1. **English only.** All documentation is written in English regardless of the language
   used in discussion, issues, or commit messages.
2. **Read the relevant document first.** Before changing code in an area, read the
   document that describes it — use the mapping below.
3. **Code and docs change together.** When behaviour changes, update the corresponding
   document in the *same commit*. A behaviour change with a stale document is an
   incomplete change.
4. **Every `docs/` folder has a `README.md`** that links to the files inside it and to
   related documents elsewhere. When adding a document, add its link to that README, to
   [docs/README.md](docs/README.md), and to the direct-links table in
   [README.md](README.md).
5. **Swagger screenshots follow the API.** The captures in
   [docs/screenshots/](docs/screenshots/README.md) are live Swagger UI responses. If a
   change alters a route, a field, a status code, an error body or the seed numbers,
   re-capture the affected PNGs in the *same commit*:
   `python scripts/capture_swagger_ui.py --only <scenario>` against a running server
   (`--only` is a substring filter; omit it to rebuild all 29 from a deleted
   `monitoring.db`). Adding or removing a capture also updates
   [docs/screenshots/README.md](docs/screenshots/README.md).

The **source → document mapping** — which document to read and update for each source
directory — is the table in
[docs/contributing/DOCUMENTATION.md](docs/contributing/DOCUMENTATION.md#5-source--document-mapping).
Read it before changing anything under `app/`. It is kept in one place so it cannot
drift; do not copy it back into this file — `scripts/check_docs_sync.py` holds the only
second copy, as `MAPPING`, and a new row goes in both.

That script is also the safety net for rule 3: a `PreToolUse` hook in
[.claude/settings.json](.claude/settings.json) runs it before every `git commit`, and it
names the documents the mapping asks for that were not staged. It warns and lets the
commit through — treat the warning as the reminder it is, not as noise, and stage the
document if the change was a behaviour change.

A change that alters observable behaviour also belongs in
[docs/demo/WALKTHROUGH.md](docs/demo/WALKTHROUGH.md) if it invalidates a step or an
expected number there.

Documentation index: [docs/README.md](docs/README.md).

## Commit conventions

Prefix every commit subject with its type:

| Prefix | Use for |
|---|---|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation |
| `refactor:` | Code refactoring |
| `test:` | Test code |

A change that alters behaviour *and* its document is one `feat:` or `fix:` commit
covering both — the documentation rule above requires them to land together, so do not
split the doc update into a separate `docs:` commit. Use `docs:` only when nothing
outside `docs/`, `README.md`, or `CLAUDE.md` changes.

**Split every push into multiple commits.** Work is never committed as one batch. Before
committing, break the working tree into a sequence of logical changes, stage each one
explicitly (`git add <paths>`, never `git add -A`), commit it with its own message, then
push the whole sequence at once. Order the commits so each one leaves the repository
working on its own — a `refactor:` that prepares the ground comes before the `feat:` that
uses it. The only work that stays a single commit is a change that cannot be split
without breaking that rule, such as a behaviour change and the document it invalidates.

Subject and body style, and how to scope a commit:
[docs/contributing/COMMITS.md](docs/contributing/COMMITS.md).

## Reference docs — fetch on demand

**FastAPI: https://fastapi.tiangolo.com/**

Before writing or changing FastAPI code, WebFetch the relevant page instead of
answering from memory. Start narrow — fetch the specific page, not the index:

- `/tutorial/` — core usage
- `/tutorial/dependencies/` — `Depends`, our auth pattern in `app/core/`
- `/tutorial/sql-databases/` — session handling with SQLAlchemy
- `/tutorial/handling-errors/` — exception handlers, used in `app/main.py`
- `/advanced/` — background tasks, custom responses, middleware
- `/reference/` — API reference for exact signatures

Secondary, same rule (fetch the page, don't guess):

- Pydantic v2: https://docs.pydantic.dev/latest/
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/en/20/
