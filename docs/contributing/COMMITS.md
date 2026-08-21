# Commit Conventions

Every commit subject starts with a type prefix.

| Prefix | Use for |
|---|---|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation |
| `refactor:` | Code refactoring |
| `test:` | Test code |

```
docs: extract business rules into docs/business-rules/
feat: add region filter to the instance list endpoint
fix: stop repeated status PATCH from resetting updatedAt
refactor: move alert dedup check into alert_service
test: cover the 48-hour long-stopped boundary
```

---

## 1. Choosing the prefix

Pick the type from **what the change does for a reader of the history**, not from which
files it touches.

| Situation | Prefix |
|---|---|
| A new endpoint, field, filter, or rule | `feat:` |
| Behaviour was wrong and is now right | `fix:` |
| Only `docs/`, `README.md`, or `CLAUDE.md` changed | `docs:` |
| Same behaviour, better structure | `refactor:` |
| Only files under `tests/` changed | `test:` |

### Code and its documentation are one commit

[DOCUMENTATION.md](DOCUMENTATION.md) requires a behaviour change and its document to
land together. So a change that alters behaviour **and** updates the corresponding
document is a single `feat:` or `fix:` commit covering both — do **not** split the
document update into a separate `docs:` commit.

```
feat: add region filter to the instance list endpoint

Adds a `region` query parameter to GET /api/instances, matched exactly and
combined with the existing filters. Documents it in api/ENDPOINTS.md and
api/CONVENTIONS.md.
```

Use `docs:` only when nothing outside `docs/`, `README.md`, or `CLAUDE.md` changes.

### When two prefixes both fit

Use the one describing the **primary** intent, and mention the rest in the body. A
refactor that also fixes a bug is a `fix:` — the bug fix is what a reader scanning the
log needs to find. A feature that required a refactor first is better split into a
`refactor:` commit followed by a `feat:` commit.

---

## 2. Writing the subject

- **Imperative mood** — `add`, `fix`, `move`, not `added` or `adds`.
- **Lowercase** after the prefix, no trailing period.
- **Around 50–72 characters.** If it will not fit, the commit is probably doing two
  things.
- **Say what changed, not which file.** `fix: stop repeated status PATCH from resetting
  updatedAt` is useful; `fix: update instance_service.py` is not.

---

## 3. Writing the body

Optional for a small, self-evident change. Required when the *why* is not obvious from
the diff.

Separate it from the subject with a blank line, wrap at 72 characters, and explain the
reasoning rather than restating the diff — the diff already says what changed. Reference
the rule or constraint that motivated it.

```
fix: stop repeated status PATCH from resetting updatedAt

An identical status update now returns the instance unchanged instead of
touching updatedAt. The 48-hour long-stopped detection and the SLA uptime
approximation both read updatedAt as the moment the status last changed, so a
client re-asserting known state was restarting that clock and hiding
long-stopped instances indefinitely.
```

---

## 4. Scope of a commit

One logical change per commit. A commit should be reviewable on its own and should not
leave the repository broken.

When a piece of work naturally splits, split it — the documentation restructure in this
repository landed as nine commits, one per folder, rather than one large one. That keeps
each diff readable and lets a bad change be reverted without taking the rest with it.

Do not mix unrelated changes into one commit because they happened at the same time.
Files you did not intend to change should stay out of the commit; stage explicitly
rather than reaching for `git add -A`.

---

## 5. Language

Commit messages are written in **English**, like all documentation in this repository,
regardless of the language used in discussion — see [DOCUMENTATION.md](DOCUMENTATION.md).

---

## 6. Related

| Document | Why |
|---|---|
| [DOCUMENTATION.md](DOCUMENTATION.md) | The rule that puts code and docs in one commit |
| [README.md](README.md) | Contributing index |
| [../../CLAUDE.md](../../CLAUDE.md) | Condensed rules loaded automatically by Claude Code |
