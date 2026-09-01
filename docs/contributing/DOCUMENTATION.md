# Documentation Rules

These apply to every change in this repository, for every contributor.

---

## 1. English only

All documentation is written in English, regardless of the language used in discussion,
issues, or commit messages. The team works in mixed languages; the written record does
not.

This covers `docs/`, `README.md`, `CLAUDE.md`, commit messages, docstrings, and code
comments.

---

## 2. Read the relevant document first

Before changing code in an area, read the document that describes it. Use the
[source → document mapping](#5-source--document-mapping) below to find it.

The rules in `docs/business-rules/` exist because several of them are non-obvious from
the code alone — the idempotent-update guard, the alert dedup condition, the SLA
approximation. Changing that code without reading the document is how a documented
guarantee gets removed by accident.

---

## 3. Code and docs change together

When behaviour changes, update the corresponding document in the **same commit**. A
behaviour change with a stale document is an incomplete change.

This is also why such a change is one `feat:` or `fix:` commit rather than a code commit
plus a separate `docs:` commit — see [COMMITS.md](COMMITS.md).

---

## 4. Every folder has a README

Every folder under `docs/` has a `README.md` that links to the files inside it and to
related documents elsewhere.

When adding a document, add its link in three places:

1. the `README.md` of its own folder,
2. the file index in [../README.md](../README.md),
3. the direct-links table in the root [README.md](../../README.md).

When adding a **folder**, give it a `README.md` and add a row for it to the folder tables
in both [../README.md](../README.md) and the root [README.md](../../README.md).

---

## 5. Source → document mapping

| When you change… | Update… |
|---|---|
| `app/controllers/**` — routes, params, status codes | [../api/ENDPOINTS.md](../api/ENDPOINTS.md), [../api/OVERVIEW.md](../api/OVERVIEW.md) |
| `app/schemas/**` — request/response fields | [../api/ENDPOINTS.md](../api/ENDPOINTS.md) |
| `app/models/**` — tables, columns, relationships | [../design/ERD.md](../design/ERD.md) |
| `app/services/instance_service.py` | [../business-rules/INSTANCE_LIFECYCLE.md](../business-rules/INSTANCE_LIFECYCLE.md) |
| `app/services/monitor_service.py`, `alert_service.py` | [../business-rules/ALERTING.md](../business-rules/ALERTING.md) |
| `app/services/client_service.py` — cost | [../business-rules/COST.md](../business-rules/COST.md) |
| `app/services/client_service.py` — SLA | [../business-rules/SLA.md](../business-rules/SLA.md) |
| `app/services/llm_service.py` | [../design/LLM_FEATURE.md](../design/LLM_FEATURE.md) |
| `app/core/**` — auth, deps, exceptions | [../api/AUTHENTICATION.md](../api/AUTHENTICATION.md), [../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md), [../api/ERRORS.md](../api/ERRORS.md) |
| `app/database.py` — engine, pool, SQLite pragmas, `get_db` | [../design/DATABASE.md](../design/DATABASE.md), [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) |
| `app/config.py` — thresholds, pricing, settings | [../business-rules/README.md](../business-rules/README.md), [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md), [../operations/CONFIGURATION.md](../operations/CONFIGURATION.md) |
| `app/seed.py` — demo data | [../demo/SEED_DATA.md](../demo/SEED_DATA.md), [../demo/ACCOUNTS.md](../demo/ACCOUNTS.md) |
| `app/main.py` — routers, handlers, startup | [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md), [../api/ERRORS.md](../api/ERRORS.md), [../operations/DEPLOYMENT.md](../operations/DEPLOYMENT.md) — § 3 describes what the startup hook does |
| `tests/**` — cases, fixtures | [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) |
| Project layout or new module | [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) |
| A function under `app/**` is added, removed, renamed or moved | [../onboarding/READING_ORDER.md](../onboarding/READING_ORDER.md) — it walks the functions in order and cites their line numbers |
| Anything visible in a Swagger response — a route, a field, a status code, an error body, seed numbers | [../screenshots/](../screenshots/README.md) — re-capture the affected PNGs ([how](#6-screenshots-follow-the-api)) |
| Anything a reader would notice — an endpoint, a status code, a rule, a document | [../changelog/CHANGELOG.md](../changelog/CHANGELOG.md) — one entry per change, in the same commit ([how to word it](../changelog/CHANGELOG.md#adding-an-entry)) |

A change that alters observable behaviour also belongs in
[../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) if it invalidates a step or an expected
number there.

---

## 6. Screenshots follow the API

The PNGs in [../screenshots/](../screenshots/README.md) are Swagger UI responses captured
against a running server, so they carry the same guarantees a document does — and go
stale the same way. A change to a route, a request body, a response field, a status code,
an error shape or the seed numbers makes the affected capture wrong. **Re-capture it in
the same commit as the change**, for the same reason rule 3 exists: a screenshot showing
a response the API no longer returns is worse than no screenshot.

Re-capture only what the change touched — `--only` is a substring filter on the scenario
name, which is the part of the filename after the number:

```bash
uvicorn app.main:app --reload                                  # terminal 1
python scripts/capture_swagger_ui.py --only instance_create    # terminal 2
```

Omit `--only` to rebuild all 29. A run has side effects on `monitoring.db` — it adds a
client and resolves an alert — so delete the file and restart the server first, otherwise
the captured numbers drift from [../demo/SEED_DATA.md](../demo/SEED_DATA.md).

If the change adds or removes a scenario, edit
[../../scripts/capture_swagger_ui.py](../../scripts/capture_swagger_ui.py) and update the
tables in [../screenshots/README.md](../screenshots/README.md); if it touches one of the
four images in the root [README.md](../../README.md) gallery, check that gallery still
shows what its caption claims.

---

## 7. The check that reminds you

Rules 2, 3 and 6 all depend on someone remembering them at the moment they commit.
[../../scripts/check_docs_sync.py](../../scripts/check_docs_sync.py) remembers for you:
it reads the staged paths, applies the mapping in [section 5](#5-source--document-mapping),
and names the documents that were not staged alongside them.

It **warns and lets the commit through**. The rule asks for a document only when
*behaviour* changes, and no script can tell a behaviour change from a rename — so it
reports candidates and leaves the judgement to you. A refactor that changes nothing
observable needs nothing; the reminder is there for the change that does.

Two entry points share the one script:

| Entry point | Covers | Setup |
|---|---|---|
| Git `pre-commit` hook — [../../scripts/hooks/pre-commit](../../scripts/hooks/pre-commit) | Every commit, by anyone | `git config core.hooksPath scripts/hooks`, once per clone |
| Claude Code `PreToolUse` hook — [../../.claude/settings.json](../../.claude/settings.json) | Commits made by an agent in this repository | None — the settings file is checked in |

Run it by hand at any time against what is currently staged:

```bash
python scripts/check_docs_sync.py
```

The mapping lives twice — as the table in section 5 and as `MAPPING` in the script — so
**a new row goes in both, in the same commit**. This file is governed by the rule it
describes.

---

## 8. Writing style

- **State the rule, then why it exists.** The reasoning is the part that cannot be
  recovered from the code.
- **Document known gaps honestly.** The SLA approximation, the unread `cost_snapshots`
  table, and the two different error body shapes are all written down precisely because
  a reader would otherwise assume they were mistakes.
- **Keep example figures verifiable.** Numbers in `docs/demo/` are asserted by the test
  suite in [../../tests/](../../tests/); if a change moves them, move the document too.
  What each suite pins down is catalogued in
  [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md).
- **Link with relative paths** so links work on GitHub and in local editors alike.

---

## 9. Related

| Document | Why |
|---|---|
| [COMMITS.md](COMMITS.md) | Commit prefixes and message structure |
| [README.md](README.md) | Contributing index |
| [../screenshots/README.md](../screenshots/README.md) | The captures rule 6 keeps current, and what each one shows |
| [../../scripts/check_docs_sync.py](../../scripts/check_docs_sync.py) | The commit-time reminder rule 7 describes |
| [../changelog/CHANGELOG.md](../changelog/CHANGELOG.md) | Where the change itself gets recorded |
| [../testing/RUNNING_TESTS.md](../testing/RUNNING_TESTS.md) | Running the suite before you commit |
| [../README.md](../README.md) | Documentation index |
| [../../CLAUDE.md](../../CLAUDE.md) | Condensed rules loaded automatically by Claude Code |
