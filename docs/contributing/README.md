# Contributing

Conventions every change in this repository follows.

| Document | Contents |
|---|---|
| [COMMITS.md](COMMITS.md) | Commit message prefixes, subject and body style, commit scope |
| [DOCUMENTATION.md](DOCUMENTATION.md) | English-only rule, read-before-you-write, code-and-docs-together, screenshots-follow-the-API, source → document mapping |

## The short version

Commit subjects carry a type prefix:

| Prefix | Use for |
|---|---|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation |
| `refactor:` | Code refactoring |
| `test:` | Test code |

Documentation is written in **English**, the document covering an area is **read before**
that area is changed, and it is **updated in the same commit** as the code. A behaviour
change plus its document is therefore one `feat:` or `fix:` commit, not a code commit
followed by a `docs:` commit.

The Swagger captures in [../screenshots/](../screenshots/README.md) count as documents:
a change that alters a response re-takes the affected images in that same commit.

None of that is enforced by a gate, but it is *reminded*:
[../../scripts/check_docs_sync.py](../../scripts/check_docs_sync.py) reads the staged
paths at commit time and names the documents the mapping asks for that were not staged.
It warns and lets the commit through — see
[DOCUMENTATION.md § 7](DOCUMENTATION.md#7-the-check-that-reminds-you) for how to install
it.

## Related

| Document | Why |
|---|---|
| [../onboarding/READING_ORDER.md](../onboarding/READING_ORDER.md) | Reading the code before changing it |
| [../changelog/CHANGELOG.md](../changelog/CHANGELOG.md) | Recording the change once you have made it |
| [../README.md](../README.md) | Documentation index — where each document lives |
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | Which layer a change belongs in |
| [../testing/RUNNING_TESTS.md](../testing/RUNNING_TESTS.md) | Running the tests before you commit |
| [../../scripts/check_docs_sync.py](../../scripts/check_docs_sync.py) | The commit-time reminder for the rule above |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | Verifying the same behaviour by hand |
| [../../CLAUDE.md](../../CLAUDE.md) | Condensed form of these rules, loaded automatically by Claude Code |
