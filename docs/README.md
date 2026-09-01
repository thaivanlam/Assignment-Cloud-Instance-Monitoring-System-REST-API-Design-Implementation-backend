# Documentation

Documentation for the TechValley Cloud Instance Monitoring System. Each folder has its
own README linking to the files inside it.

| Folder | Contents |
|---|---|
| [onboarding/](onboarding/README.md) | How to read this codebase for the first time |
| [requirements/](requirements/README.md) | BRD, SRS, FRS and the use case / user story specification |
| [api/](api/README.md) | Overview, authentication, request conventions, errors, per-endpoint reference |
| [business-rules/](business-rules/README.md) | Authorization, instance lifecycle, alerting, cost, SLA |
| [manual/](manual/README.md) | End-user manual for operating the system |
| [demo/](demo/README.md) | Demo accounts, seed data, step-by-step walkthrough |
| [design/](design/README.md) | Architecture, ERD, database engine, LLM feature design |
| [testing/](testing/README.md) | Functional test suite and how to run it |
| [performance/](performance/README.md) | Measured latency, throughput and concurrency findings |
| [security/](security/README.md) | Reproduced injection, disclosure and session findings |
| [operations/](operations/README.md) | Deploying, configuring and troubleshooting a running deployment |
| [team/](team/README.md) | Per-member assignment scope |
| [contributing/](contributing/README.md) | Commit conventions and documentation rules |
| [changelog/](changelog/README.md) | What changed in this repository, and when |
| [screenshots/](screenshots/README.md) | Captured Swagger UI responses |

---

## Where to start

| If you want to… | Read |
|---|---|
| Read the source for the first time | [onboarding/READING_ORDER.md](onboarding/READING_ORDER.md) |
| Know what the system was built to do, and for whom | [requirements/BRD.md](requirements/BRD.md) → [requirements/SRS.md](requirements/SRS.md) |
| Look up exactly how one function must behave | [requirements/FRS.md](requirements/FRS.md) |
| Use the system as an operator | [manual/USER_MANUAL.md](manual/USER_MANUAL.md) |
| Run the API and click through it | [demo/README.md](demo/README.md) → [demo/WALKTHROUGH.md](demo/WALKTHROUGH.md) |
| Call an endpoint from client code | [api/AUTHENTICATION.md](api/AUTHENTICATION.md) → [api/ENDPOINTS.md](api/ENDPOINTS.md) |
| Understand *why* a response looks that way | [business-rules/README.md](business-rules/README.md) |
| Change or extend the code | [design/ARCHITECTURE.md](design/ARCHITECTURE.md) → [design/ERD.md](design/ERD.md) |
| Know which database a run opens | [design/DATABASE.md](design/DATABASE.md) |
| Work on the AI diagnosis feature | [design/LLM_FEATURE.md](design/LLM_FEATURE.md) |
| Run the tests, or add one | [testing/RUNNING_TESTS.md](testing/RUNNING_TESTS.md) → [testing/FUNCTIONAL_TESTS.md](testing/FUNCTIONAL_TESTS.md) |
| Check a case by hand, or trace a requirement to its test | [testing/TEST_CASES.md](testing/TEST_CASES.md) |
| Know what is slow, and why | [performance/PERFORMANCE_BUGS.md](performance/PERFORMANCE_BUGS.md) |
| Know what is exposed, and why | [security/SECURITY_BUGS.md](security/SECURITY_BUGS.md) |
| Deploy it somewhere, or configure its keys | [operations/DEPLOYMENT.md](operations/DEPLOYMENT.md) → [operations/CONFIGURATION.md](operations/CONFIGURATION.md) |
| Fix a server that will not start, or stopped answering | [operations/RUNBOOKS.md](operations/RUNBOOKS.md) |
| Commit a change | [contributing/COMMITS.md](contributing/COMMITS.md) |
| See what changed, and when | [changelog/CHANGELOG.md](changelog/CHANGELOG.md) |

---

## Full file index

**[onboarding/](onboarding/README.md)**

- [READING_ORDER.md](onboarding/READING_ORDER.md) — function-by-function reading path through `app/`, in call-dependency order

**[requirements/](requirements/README.md)**

- [BRD.md](requirements/BRD.md) — business context, objectives, stakeholders, scope, 19 business requirements, known shortfalls, risks
- [SRS.md](requirements/SRS.md) — functional requirements FR-01…FR-10, non-functional requirements, interfaces, data requirements, verification
- [FRS.md](requirements/FRS.md) — 24 function specs: inputs, processing rules, outputs, failure paths
- [USE_CASES.md](requirements/USE_CASES.md) — 15 use cases with alternative flows, 30 user stories with acceptance criteria

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

**[manual/](manual/README.md)**

- [USER_MANUAL.md](manual/USER_MANUAL.md) — operating the system task by task, with an error-message reference and an FAQ

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

- [TEST_CASES.md](testing/TEST_CASES.md) — case specification: preconditions, steps, data, expected results, priority, traceability
- [FUNCTIONAL_TESTS.md](testing/FUNCTIONAL_TESTS.md) — test approach, fixtures, suite catalogue, coverage, gaps
- [RUNNING_TESTS.md](testing/RUNNING_TESTS.md) — install, run, select tests, read a failure, troubleshooting

**[performance/](performance/README.md)**

- [PERFORMANCE_BUGS.md](performance/PERFORMANCE_BUGS.md) — 15 measured performance findings, ranked, with fixes

**[security/](security/README.md)**

- [SECURITY_BUGS.md](security/SECURITY_BUGS.md) — 15 reproduced security findings, ranked, with fixes and what was found sound

**[operations/](operations/README.md)**

- [DEPLOYMENT.md](operations/DEPLOYMENT.md) — launching locally, on a server and on Vercel; verification, upgrade, rollback, backup
- [CONFIGURATION.md](operations/CONFIGURATION.md) — every setting, generating the keys, and what a rotation breaks
- [RUNBOOKS.md](operations/RUNBOOKS.md) — 15 incident runbooks: symptom, cause, fix, verification

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
- **Swagger screenshots follow the API.** A change that alters a response re-captures
  the affected images in [screenshots/](screenshots/README.md), in the same commit.
- **Commit subjects carry a type prefix** — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`.
- **A commit-time check reminds you.** `scripts/check_docs_sync.py` names the documents
  the mapping asks for that were not staged. It warns; it does not block.

Full rules, including the source → document mapping:
[contributing/DOCUMENTATION.md](contributing/DOCUMENTATION.md) and
[contributing/COMMITS.md](contributing/COMMITS.md).
