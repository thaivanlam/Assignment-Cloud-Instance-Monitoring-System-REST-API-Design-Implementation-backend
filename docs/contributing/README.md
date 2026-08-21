# Contributing

Conventions every change in this repository follows.

| Document | Contents |
|---|---|
| [COMMITS.md](COMMITS.md) | Commit message prefixes, subject and body style, commit scope |
| [DOCUMENTATION.md](DOCUMENTATION.md) | English-only rule, read-before-you-write, code-and-docs-together, source → document mapping |

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

## Related

| Document | Why |
|---|---|
| [../README.md](../README.md) | Documentation index — where each document lives |
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | Which layer a change belongs in |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | Running the tests before you commit |
| [../../CLAUDE.md](../../CLAUDE.md) | Condensed form of these rules, loaded automatically by Claude Code |
