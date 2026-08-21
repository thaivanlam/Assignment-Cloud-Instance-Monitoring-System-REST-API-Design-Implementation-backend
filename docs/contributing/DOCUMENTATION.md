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
| `app/config.py` — thresholds, pricing | [../business-rules/README.md](../business-rules/README.md), [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) |
| `app/seed.py` — demo data | [../demo/SEED_DATA.md](../demo/SEED_DATA.md), [../demo/ACCOUNTS.md](../demo/ACCOUNTS.md) |
| `app/main.py` — routers, handlers, startup | [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md), [../api/ERRORS.md](../api/ERRORS.md) |
| `tests/**` — cases, fixtures | [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) |
| Project layout or new module | [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) |

A change that alters observable behaviour also belongs in
[../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) if it invalidates a step or an expected
number there.

---

## 6. Writing style

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

## 7. Related

| Document | Why |
|---|---|
| [COMMITS.md](COMMITS.md) | Commit prefixes and message structure |
| [README.md](README.md) | Contributing index |
| [../testing/RUNNING_TESTS.md](../testing/RUNNING_TESTS.md) | Running the suite before you commit |
| [../README.md](../README.md) | Documentation index |
| [../../CLAUDE.md](../../CLAUDE.md) | Condensed rules loaded automatically by Claude Code |
