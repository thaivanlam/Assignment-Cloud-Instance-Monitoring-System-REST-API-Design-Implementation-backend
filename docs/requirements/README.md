# Requirements

What the system is *for*, what it must do, and how each function behaves — the
specification layer above the API reference and the business rules.

| Document | Contents |
|---|---|
| [BRD.md](BRD.md) | **Business Requirements Document** — business context, objectives, stakeholders, scope, 19 business requirements, the numbers behind the rules, known shortfalls, risks |
| [SRS.md](SRS.md) | **Software Requirements Specification** — functional requirements FR-01…FR-10, non-functional requirements (performance, security, reliability, maintainability, portability, usability), interfaces, data requirements, verification |
| [FRS.md](FRS.md) | **Functional Requirements Specification** — 24 function specs: inputs and validation, processing rules in order, outputs, every failure path |
| [USE_CASES.md](USE_CASES.md) | **Use cases and user stories** — 15 use cases with main and alternative flows, 30 user stories with Given/When/Then acceptance criteria |

## Reading order

1. **[BRD.md](BRD.md)** — why the system exists and what the business asked for.
2. **[SRS.md](SRS.md)** — what the software must do, and how well.
3. **[FRS.md](FRS.md)** — exactly how each function behaves.
4. **[USE_CASES.md](USE_CASES.md)** — the same ground as scenarios, if you think in flows
   rather than in functions.

A reader who only wants to *call* the API should skip all four and start at
[../api/README.md](../api/README.md).

## How these relate to the rest of the documentation

These documents are **specification**: what must be true. The rest of `docs/` records what
*is* true and why:

| These say | The delivered system is described in |
|---|---|
| A function must accept these inputs and answer with these fields | [../api/ENDPOINTS.md](../api/ENDPOINTS.md) |
| A rule must hold | [../business-rules/](../business-rules/README.md) — the same rule with its implementation and reasoning |
| A requirement must be verified | [../testing/TEST_CASES.md](../testing/TEST_CASES.md) and [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) |
| An operator must be able to do this | [../manual/USER_MANUAL.md](../manual/USER_MANUAL.md) |

They were written **against the delivered system**, so they describe what the code does
rather than what was hoped for it. Where a requirement is only partly met — SLA accuracy
is the clear case — it says so and links to the limitation instead of claiming success.

Traceability runs end to end: **BR** ([BRD § 12](BRD.md#12-traceability)) → **FR/NFR**
([SRS § 8](SRS.md#8-traceability)) → **F-\*** ([FRS](FRS.md#function-index)) → **UC/US**
([USE_CASES § 6](USE_CASES.md#6-traceability)) → **TC**
([TEST_CASES § 9](../testing/TEST_CASES.md#9-traceability-matrix)).

## Related

| Document | Why |
|---|---|
| [../api/README.md](../api/README.md) | The delivered interface these documents specify |
| [../business-rules/README.md](../business-rules/README.md) | The rules, with the reasoning behind each |
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | How the constraints in [SRS § 2.5](SRS.md#25-design-and-implementation-constraints) are realised |
| [../design/ERD.md](../design/ERD.md) | The data model behind [SRS § 6](SRS.md#6-data-requirements) |
| [../testing/TEST_CASES.md](../testing/TEST_CASES.md) | The verification layer |
| [../manual/USER_MANUAL.md](../manual/USER_MANUAL.md) | The end-user view of the same functions |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | The use cases, run against real seeded numbers |
