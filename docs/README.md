# Documentation

Documentation for the TechValley Cloud Instance Monitoring System. Each folder has its
own README linking to the files inside it.

| Folder | Contents |
|---|---|
| [onboarding/](onboarding/README.md) | How to read this codebase for the first time |
| [api/](api/README.md) | Overview, authentication, request conventions, errors, per-endpoint reference |
| [business-rules/](business-rules/README.md) | Authorization, instance lifecycle, alerting, cost, SLA |
| [demo/](demo/README.md) | Demo accounts, seed data, step-by-step walkthrough |
| [design/](design/README.md) | Architecture, ERD, database engine, LLM feature design |
| [testing/](testing/README.md) | Functional test suite and how to run it |
| [performance/](performance/README.md) | Measured latency, throughput and concurrency findings |
| [team/](team/README.md) | Per-member assignment scope |
| [contributing/](contributing/README.md) | Commit conventions and documentation rules |
| [changelog/](changelog/README.md) | What changed in this repository, and when |
| [screenshots/](screenshots/README.md) | Captured Swagger UI responses |

---

## Where to start

| If you want to… | Read |
|---|---|
| Read the source for the first time | [onboarding/READING_ORDER.md](onboarding/READING_ORDER.md) |
| Run the API and click through it | [demo/README.md](demo/README.md) → [demo/WALKTHROUGH.md](demo/WALKTHROUGH.md) |
| Call an endpoint from client code | [api/AUTHENTICATION.md](api/AUTHENTICATION.md) → [api/ENDPOINTS.md](api/ENDPOINTS.md) |
| Understand *why* a response looks that way | [business-rules/README.md](business-rules/README.md) |
| Change or extend the code | [design/ARCHITECTURE.md](design/ARCHITECTURE.md) → [design/ERD.md](design/ERD.md) |
| Know which database a run opens | [design/DATABASE.md](design/DATABASE.md) |
| Work on the AI diagnosis feature | [design/LLM_FEATURE.md](design/LLM_FEATURE.md) |
| Run the tests, or add one | [testing/RUNNING_TESTS.md](testing/RUNNING_TESTS.md) → [testing/FUNCTIONAL_TESTS.md](testing/FUNCTIONAL_TESTS.md) |
| Know what is slow, and why | [performance/PERFORMANCE_BUGS.md](performance/PERFORMANCE_BUGS.md) |
| Commit a change | [contributing/COMMITS.md](contributing/COMMITS.md) |
| See what changed, and when | [changelog/CHANGELOG.md](changelog/CHANGELOG.md) |

---

## Full file index

**[onboarding/](onboarding/README.md)**

- [READING_ORDER.md](onboarding/READING_ORDER.md) — function-by-function reading path through `app/`, in call-dependency order

**[api/](api/README.md)**

- [OVERVIEW.md](api/OVERVIEW.md) — base URL, endpoint map, enumerations, naming
- [AUTHENTICATION.md](api/AUTHENTICATION.md) — login, JWT claims, Swagger authorization
- [CONVENTIONS.md](api/CONVENTIONS.md) — pagination, filtering, sorting, timestamps
- [ERRORS.md](api/ERRORS.md) — status codes and error body shapes
- [ENDPOINTS.md](api/ENDPOINTS.md) — per-endpoint request/response reference

**[business-rules/](business-rules/README.md)**

- [AUTHORIZATION.md](business-rules/AUTHORIZATION.md) — roles, client scoping, `403` vs `404`
- [INSTANCE_LIFECYCLE.md](business-rules/INSTANCE_LIFECYCLE.md) — registration, transitions, RUNNING delete block
- [ALERTING.md](business-rules/ALERTING.md) — thresholds, auto-recording, duplicate prevention
- [COST.md](business-rules/COST.md) — unit pricing, current cost, forecast
- [SLA.md](business-rules/SLA.md) — plan thresholds, uptime approximation

**[demo/](demo/README.md)**

- [ACCOUNTS.md](demo/ACCOUNTS.md) — credentials and client ownership
- [SEED_DATA.md](demo/SEED_DATA.md) — seeded members, clients, instances, totals
- [WALKTHROUGH.md](demo/WALKTHROUGH.md) — 29-step demo script

**[design/](design/README.md)**

- [ARCHITECTURE.md](design/ARCHITECTURE.md) — MVC layering, request flow, configuration
- [ERD.md](design/ERD.md) — entity relationship diagram and schema notes
- [DATABASE.md](design/DATABASE.md) — engine and pool per `DATABASE_URL`, where in-memory SQLite is used
- [LLM_FEATURE.md](design/LLM_FEATURE.md) — diagnosis endpoint design

**[testing/](testing/README.md)**

- [FUNCTIONAL_TESTS.md](testing/FUNCTIONAL_TESTS.md) — test approach, fixtures, suite catalogue, coverage, gaps
- [RUNNING_TESTS.md](testing/RUNNING_TESTS.md) — install, run, select tests, read a failure, troubleshooting

**[performance/](performance/README.md)**

- [PERFORMANCE_BUGS.md](performance/PERFORMANCE_BUGS.md) — 15 measured performance findings, ranked, with fixes

**[team/](team/README.md)**

- [MEMBER_C.md](team/MEMBER_C.md) — instance status and monitoring scope

**[contributing/](contributing/README.md)**

- [COMMITS.md](contributing/COMMITS.md) — commit prefixes, subject and body style, commit scope
- [DOCUMENTATION.md](contributing/DOCUMENTATION.md) — documentation rules and source → document mapping

**[changelog/](changelog/README.md)**

- [CHANGELOG.md](changelog/CHANGELOG.md) — dated record of every noticeable change, newest first, each entry citing its commit

---

## Conventions for these documents

- **English only**, regardless of the language used in discussion.
- **Code and docs change together.** A change that alters behaviour updates the
  document describing that behaviour in the same commit.
- **Read before you write.** Consult the document covering the area you are about to
  change before changing it.
- **Every folder has a README** linking to its files and to related documents elsewhere.
- **Commit subjects carry a type prefix** — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`.

Full rules, including the source → document mapping:
[contributing/DOCUMENTATION.md](contributing/DOCUMENTATION.md) and
[contributing/COMMITS.md](contributing/COMMITS.md).
