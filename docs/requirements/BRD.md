# Business Requirements Document

| | |
|---|---|
| System | TechValley Cloud Instance Monitoring System |
| Document | Business Requirements Document (BRD) |
| Status | Baseline — describes the delivered system |
| Owner | TechValley Developer Track team |
| Last reviewed | 2026-09-01 |

Business goals, stakeholder needs, and the overall scope of the project — *what* the
business needs and *why*. How the software satisfies it is [SRS.md](SRS.md); what each
function does, field by field, is [FRS.md](FRS.md).

---

## 0. How to read this document

This BRD was written **against the delivered system**, not ahead of it. Every requirement
below is one the running API satisfies, and each row cites the document that specifies it.
Requirements that were considered and deliberately left out are listed in
[§ 10](#10-deliberate-exclusions) rather than quietly dropped.

That direction of authorship is the document's main safeguard: it cannot promise more than
the code does. Where a business need is only *partly* met — SLA reporting is the clear
case — the row says so and links to the limitation.

---

## 1. Business context

TechValley is a managed cloud-services company. It operates cloud instances on behalf of
**10 client companies**, each on a contract plan that carries an uptime commitment. Two
client managers divide the accounts between them, under one operations administrator.

Before this system, the whole inventory lived in a shared spreadsheet. Six problems came
out of that, and they are the reason the project exists:

| | Problem | Consequence |
|---|---|---|
| **P1** | One spreadsheet, no access boundary | Every manager could read and edit every other manager's client data. A mistake in one account could silently damage another. |
| **P2** | Nothing detected anything | An overloaded or failed instance was noticed when the client phoned. Detection depended on a person opening the file. |
| **P3** | Cost totals were retyped by hand | Per-client monthly totals were recalculated manually, so they were stale, inconsistent between managers, and unusable in a budget conversation. |
| **P4** | Contract uptime could not be evidenced | The contract plans promise 99.9% / 99% / 95%. Nothing measured whether they were met. |
| **P5** | No incident record | After a problem was handled, nothing recorded that it had happened, or who dealt with it. |
| **P6** | No first-line guidance | A junior on-call engineer facing a failed instance waited for a senior engineer before doing anything. |

---

## 2. Business objectives

| | Objective | Measure of success |
|---|---|---|
| **BO-1** | Replace the spreadsheet with one system of record for every client instance | Every instance, client and manager relationship is held in one database; no parallel spreadsheet is needed to answer "what do we run for this client?" |
| **BO-2** | Detect trouble without anyone looking for it | Overloaded, failed and idle instances are found by a scan and recorded as alerts, not by eye |
| **BO-3** | Make cost visible per client, and predictable | Current-month cost and a next-month forecast are produced by the system, per client, on demand |
| **BO-4** | Evidence the contractual uptime commitment | Every client's uptime is reported against its plan's threshold, with a violation flag |
| **BO-5** | Enforce the boundary between managers | A manager reaches only their own clients' data, on every endpoint, without a per-endpoint rule to forget |
| **BO-6** | Shorten the time between an incident and the first action | On-call staff get a written probable-cause and recommended-action list for an unhealthy instance immediately |

---

## 3. Stakeholders

| Stakeholder | Role in the business | What they need from the system |
|---|---|---|
| **Operations administrator** | Owns the whole estate; onboards client companies | Unrestricted visibility; the only role that may register a client |
| **Client manager** | Responsible for a set of client accounts | Their own clients' instances, alerts, cost and SLA — and confidence they cannot damage another manager's account |
| **On-call engineer** | Responds to incidents | A current list of what is broken, a durable record of it, and first-line guidance |
| **Finance / account management** | Bills clients, negotiates renewals | Per-client monthly cost and a defensible next-month figure |
| **Client company** | Buys the contract plan | Uptime against the plan it pays for. *Clients do not use the system directly* — their manager reports from it |
| **Development team** | Builds and maintains the API | An unambiguous specification, and rules recorded with the reasoning behind them |

---

## 4. Scope

### 4.1 In scope

- Authentication and two roles, with client-level data scoping.
- The instance register: create, list, filter, sort, read, change status, delete.
- Automated detection of three conditions — high CPU, failed, long-stopped — with alerts.
- An alert history and manual resolution.
- Client registration and per-client listings.
- Current-month cost, next-month forecast and SLA reporting per client.
- An AI-assisted incident diagnosis for a single instance.
- A self-documenting HTTP interface (Swagger UI) usable for demonstration and support.

### 4.2 Out of scope

Stated explicitly, because each is the kind of thing a reader may assume is present:

| Not in scope | What that means in practice |
|---|---|
| **Controlling real infrastructure** | The system is a *record* of cloud instances. `PATCH /api/instances/{id}/status` records that an instance is stopped; it does not stop a machine at a cloud provider. Nothing here provisions, starts or terminates real resources. |
| **Invoicing** | Cost is reported, not billed. No invoice, payment or ledger exists. |
| **Notification delivery** | Alerts are recorded and readable. Nothing sends email, SMS or chat messages. |
| **Background scheduling** | There is no scheduler or worker. Detection runs when a monitoring endpoint is called — see [BR-07](#5-business-requirements). |
| **Client-facing logins** | Only TechValley staff have accounts. Client companies are data, not users. |
| **Self-service account management** | No sign-up, password reset, profile edit or logout. Members are created by the seed. |
| **Metered / hourly billing** | Pricing is a flat monthly figure per instance size. |
| **Historical status tracking** | Only the *last* status change is stored, which is what limits SLA accuracy — see [BR-13](#5-business-requirements). |

---

## 5. Business requirements

Priority uses MoSCoW: **M**ust / **S**hould / **C**ould.

| ID | Requirement | Pri | Serves | Specified in |
|---|---|:--:|---|---|
| **BR-01** | Every cloud instance is held in one system of record, attributed to exactly one client company | M | BO-1 | [FRS § F-INST-01](FRS.md#f-inst-01--register-an-instance), [ERD](../design/ERD.md) |
| **BR-02** | Every client company has exactly one responsible client manager | M | BO-1, BO-5 | [FRS § F-CLNT-01](FRS.md#f-clnt-01--register-a-client) |
| **BR-03** | A client manager can reach only the clients assigned to them, and those clients' instances and alerts | M | BO-5 | [AUTHORIZATION](../business-rules/AUTHORIZATION.md) |
| **BR-04** | An administrator can reach every client and every instance | M | BO-1 | [AUTHORIZATION § 1](../business-rules/AUTHORIZATION.md#1-roles) |
| **BR-05** | Only an administrator may onboard a client company | M | BO-5 | [AUTHORIZATION § 5](../business-rules/AUTHORIZATION.md#5-admin-only-client-registration) |
| **BR-06** | Staff must authenticate before reading or changing anything | M | BO-5 | [AUTHENTICATION](../api/AUTHENTICATION.md) |
| **BR-07** | Instances running hot, failed, or idle for a long time are detected by the system rather than by a person | M | BO-2 | [ALERTING § 1](../business-rules/ALERTING.md#1-alert-types-and-detection-conditions) |
| **BR-08** | A detected condition leaves a durable record that survives until a person marks it handled | M | BO-2 | [ALERTING § 4](../business-rules/ALERTING.md#4-resolution) |
| **BR-09** | Repeated detection of the same ongoing problem must not flood the record | M | BO-2 | [ALERTING § 3](../business-rules/ALERTING.md#3-duplicate-prevention) |
| **BR-10** | A single view answers "what is the state of the estate right now?" | S | BO-2 | [FRS § F-MON-04](FRS.md#f-mon-04--aggregate-monitoring-report) |
| **BR-11** | Per-client monthly cost is produced by the system, including instances that are stopped but still provisioned | M | BO-3 | [COST § 3](../business-rules/COST.md#3-current-month-cost--get-apiclientsidcost) |
| **BR-12** | A next-month forecast is available for budget conversations, counting only what is actually running | S | BO-3 | [COST § 4](../business-rules/COST.md#4-next-month-forecast--get-apiclientsidcost-forecast) |
| **BR-13** | Uptime is reported per client against its contract plan, with violations flagged | M | BO-4 | [SLA](../business-rules/SLA.md) — **partially met**, see [§ 7](#7-known-shortfalls-against-these-requirements) |
| **BR-14** | A live instance cannot be removed from the register by accident | M | BO-1 | [INSTANCE_LIFECYCLE § 3.1](../business-rules/INSTANCE_LIFECYCLE.md#31-running-instances-are-protected) |
| **BR-15** | Recorded state must not decay because a client tool re-sends what it already knows | M | BO-2, BO-4 | [INSTANCE_LIFECYCLE § 2.2](../business-rules/INSTANCE_LIFECYCLE.md#22-idempotent-updates) |
| **BR-16** | On-call staff get first-line written guidance for an unhealthy instance | S | BO-6 | [LLM_FEATURE](../design/LLM_FEATURE.md) |
| **BR-17** | The guidance feature must never be the reason an operator gets no answer | M | BO-6 | [LLM_FEATURE](../design/LLM_FEATURE.md) — rule-based fallback |
| **BR-18** | No response may grow without bound as the estate and its history grow | S | BO-1 | [CONVENTIONS § 1](../api/CONVENTIONS.md#1-pagination) |
| **BR-19** | The interface must be demonstrable and self-documenting to a non-author | C | BO-1 | Swagger UI at `/docs`, [USER_MANUAL](../manual/USER_MANUAL.md) |

**BR-15 deserves its own line** because it is not obvious as a *business* requirement. The
only record of when an instance last changed state is one timestamp, and both the
idle-instance rule and the uptime figure read it. A monitoring tool that re-asserts known
state every minute would keep pushing that timestamp forward, and an instance stopped for
a week would never be reported as idle. The rule that a no-change update changes nothing
is what protects two other business outcomes.

---

## 6. Business rules — the numbers, and why they are those numbers

These are business decisions, not technical ones. All are settings in
[app/config.py](../../app/config.py) and can be changed per deployment without a code
change ([CONFIGURATION](../operations/CONFIGURATION.md)).

| Rule | Value | Reasoning |
|---|---|---|
| CPU warning threshold | **80%** | The point at which an instance is judged to be running out of headroom rather than merely busy |
| Idle threshold | **48 hours** stopped | Long enough that a weekend maintenance stop is not reported as waste; short enough that a forgotten instance is caught within the billing month |
| Unit price — SMALL / MEDIUM / LARGE | **$50 / $120 / $250** per month | Flat committed monthly contract prices. The business sells capacity by size, not by the hour |
| SLA threshold — PREMIUM / STANDARD / BASIC | **99.9% / 99% / 95%** | The three contract tiers sold to clients |
| Cost includes stopped instances | Yes | A provisioned instance is committed spend for the month whether or not it runs |
| Forecast includes running instances only | Yes | A stopped instance is the operator's signal that it is on its way out |
| Alert resolution | Manual only | Auto-closing an alert when the condition clears would erase the evidence that the incident happened |

---

## 7. Known shortfalls against these requirements

Recorded here rather than in a technical appendix, because they change what a stakeholder
may claim from the output.

| Requirement | Shortfall | Effect on the business |
|---|---|---|
| **BR-13** SLA reporting | Uptime is an approximation. The system stores only the most recent status change, so an instance that failed and recovered three times this month is credited with full uptime | The figure is **indicative, not contractual**. It is sound for spotting a client currently in trouble; it must not be quoted to a client as measured downtime. The fix is a status-history table — [SLA § 3.1](../business-rules/SLA.md#31-what-the-approximation-gets-wrong) |
| **BR-07** Detection | Detection runs when someone calls a monitoring endpoint; there is no scheduler | Nothing is detected on a quiet Sunday unless a dashboard is polling. Operationally the answer is a polling dashboard; architecturally a scheduler is [out of scope](#42-out-of-scope) |
| **BR-08** Incident record | Alerts are deleted with their instance | Deleting an instance erases its incident history. Acceptable while the register is the point; not acceptable if that history ever becomes an audit record |
| **BR-11** Cost history | Month-over-month cost is designed for but not implemented — the `cost_snapshots` table is written by the seed and read by nothing | Cost questions can be answered for *now*, not for *last quarter* |
| **BR-03 / BR-06** Access control | Fifteen security findings are recorded, two rated critical, none fixed | The boundary holds against ordinary mistakes, not against an attacker. Before any deployment outside a trusted network, work through [SECURITY_BUGS](../security/SECURITY_BUGS.md) |

---

## 8. Assumptions

1. Members are trusted staff of one company; the threat model is mistake, not malice.
2. The number of clients and instances stays in the low thousands — a single-file
   database is adequate at that size.
3. Instance state reaches the system because an operator or an automation calls the API.
   Nothing polls a cloud provider.
4. Prices and SLA thresholds change rarely, and a change applies to instances registered
   *after* it — existing instances keep the price they were registered at
   ([COST § 2](../business-rules/COST.md#2-monthlycost-is-derived-but-stored)).
5. One client company is managed by exactly one manager at a time.

---

## 9. Constraints

| Constraint | Origin |
|---|---|
| REST over HTTP, JSON bodies, camelCase field names | Assignment specification — the field names mirror it exactly, at both the API and the database layer |
| Python / FastAPI / SQLAlchemy / SQLite | Assignment technology stack |
| Field naming may not be changed to snake_case | Same — it is a contract with the specification, not a style choice |
| No paid service may be required to run the system | The LLM feature must work with no API key configured ([BR-17](#5-business-requirements)) |
| Delivered as an assignment for the TechValley Developer Track | Scope is bounded by what can be demonstrated in a walkthrough and covered by tests |

---

## 10. Deliberate exclusions

Things a reader might expect, and the reason each is absent:

| Excluded | Reason |
|---|---|
| Notifications (email / chat) | No delivery infrastructure is in scope; alerts are pulled, not pushed |
| A scheduler for detection | No background worker in scope; the monitoring endpoints are the trigger |
| Auto-resolution of alerts when a condition clears | Would erase the record that the incident happened ([ALERTING § 4](../business-rules/ALERTING.md#4-resolution)) |
| Soft delete / audit trail | The register describes what exists now; history is a phase-2 concern |
| Refresh tokens, logout, revocation | Tokens are short-lived and stateless; revocation is [SEC-04](../security/SECURITY_BUGS.md) and blocked on a token identifier |
| Per-endpoint permission matrix | Two roles and one scoping rule cover every case; a matrix would add configuration without adding capability |
| `404` instead of `403` for another manager's resource | Deliberate: an internal tool where a truthful `403` makes a misassigned client obvious ([AUTHORIZATION § 3](../business-rules/AUTHORIZATION.md#3-403-rather-than-404)) |

### Phase-2 candidates, in the order they would pay off

1. **`instance_status_history`** — makes SLA exact, and BR-13 fully met.
2. **A scheduler** for detection, removing the dependence on someone calling a `GET`.
3. **Cost snapshot reporting** — the table already exists and is populated.
4. **Notification delivery** for critical alerts.
5. **The security findings register**, worked through in its stated order.

---

## 11. Risks

| Risk | Impact | Mitigation in place |
|---|---|---|
| SLA figures quoted to a client as measured | Contractual dispute | The limitation is documented at every level, and the response exposes `measuredHours` and `runningHours` per instance so the number can be audited rather than trusted |
| Detection silently stops because nothing polls | Incidents go unseen | Documented as a shortfall; a polling dashboard is the operational answer |
| The alert table grows without bound — nothing prunes it | Slow queries, unusable history | Every listing is paginated and the report's embedded list is capped at 20 |
| Default signing key left in place in a deployment | Complete authentication bypass | Documented as [SEC-01](../security/SECURITY_BUGS.md), with the rotation procedure in [CONFIGURATION](../operations/CONFIGURATION.md) |
| Price change assumed to be retroactive | Wrong figures in a finance conversation | Stated in [assumption 4](#8-assumptions) and in [COST § 2](../business-rules/COST.md#2-monthlycost-is-derived-but-stored) |

---

## 12. Traceability

Business requirement → the software requirement that carries it → the function that
implements it. Test-level traceability continues in
[../testing/TEST_CASES.md](../testing/TEST_CASES.md).

| BR | SRS | FRS | Use case |
|---|---|---|---|
| BR-01 | FR-03 | F-INST-01, F-INST-02 | [UC-03](USE_CASES.md#uc-03--register-an-instance) |
| BR-02 | FR-02 | F-CLNT-01 | [UC-02](USE_CASES.md#uc-02--onboard-a-client-company) |
| BR-03, BR-04 | FR-01, NFR-SEC-02 | F-X-02 | [UC-01](USE_CASES.md#uc-01--sign-in) |
| BR-05 | NFR-SEC-02 | F-CLNT-01 | [UC-02](USE_CASES.md#uc-02--onboard-a-client-company) |
| BR-06 | FR-01, NFR-SEC-01 | F-AUTH-01, F-AUTH-02 | [UC-01](USE_CASES.md#uc-01--sign-in) |
| BR-07 | FR-05 | F-MON-01, F-MON-02, F-MON-03 | [UC-07](USE_CASES.md#uc-07--find-overloaded-instances), [UC-08](USE_CASES.md#uc-08--find-failed-instances), [UC-09](USE_CASES.md#uc-09--find-idle-instances) |
| BR-08, BR-09 | FR-06 | F-MON-01…03, F-ALRT-02 | [UC-11](USE_CASES.md#uc-11--work-the-alert-queue) |
| BR-10 | FR-05 | F-MON-04 | [UC-10](USE_CASES.md#uc-10--read-the-morning-report) |
| BR-11, BR-12 | FR-07 | F-CLNT-04, F-CLNT-05 | [UC-12](USE_CASES.md#uc-12--report-a-clients-monthly-cost), [UC-13](USE_CASES.md#uc-13--forecast-next-months-cost) |
| BR-13 | FR-08 | F-CLNT-06 | [UC-14](USE_CASES.md#uc-14--check-a-clients-sla) |
| BR-14, BR-15 | FR-04 | F-INST-04, F-INST-05 | [UC-05](USE_CASES.md#uc-05--change-an-instances-status), [UC-06](USE_CASES.md#uc-06--retire-an-instance) |
| BR-16, BR-17 | FR-09 | F-DIAG-01 | [UC-15](USE_CASES.md#uc-15--diagnose-an-unhealthy-instance) |
| BR-18 | NFR-PERF-03 | F-X-01 | every listing use case |
| BR-19 | NFR-USE-01 | — | [USER_MANUAL](../manual/USER_MANUAL.md) |

---

## 13. Glossary

| Term | Meaning here |
|---|---|
| **Instance** | One cloud virtual machine recorded in the register, owned by one client |
| **Client / client company** | A company TechValley operates instances for. Data, not a user |
| **Member** | A TechValley staff account that can log in — `ADMIN` or `CLIENT_MANAGER` |
| **Contract plan** | `BASIC` / `STANDARD` / `PREMIUM` — sets the client's SLA threshold |
| **Alert** | A recorded detection of one of the three conditions, open until resolved |
| **Scan** | One call to a monitoring endpoint: it returns matching instances *and* records their alerts |
| **Warning** | A `RUNNING` instance at or above the CPU threshold |
| **Long-stopped / idle** | `STOPPED` for at least 48 hours |
| **Forecast** | Next calendar month's cost, assuming the currently running mix continues |
| **Violation** | A client's uptime below its plan's threshold |

---

## 14. Related

| Document | Why |
|---|---|
| [SRS.md](SRS.md) | How the software meets these requirements — functional and non-functional |
| [FRS.md](FRS.md) | Function-by-function specification |
| [USE_CASES.md](USE_CASES.md) | The same requirements as user-visible scenarios |
| [../business-rules/](../business-rules/README.md) | The rules in [§ 6](#6-business-rules--the-numbers-and-why-they-are-those-numbers), with their implementation |
| [../manual/USER_MANUAL.md](../manual/USER_MANUAL.md) | How a stakeholder operates the delivered system |
| [../security/SECURITY_BUGS.md](../security/SECURITY_BUGS.md) | The open findings behind the BR-03 / BR-06 shortfall |
