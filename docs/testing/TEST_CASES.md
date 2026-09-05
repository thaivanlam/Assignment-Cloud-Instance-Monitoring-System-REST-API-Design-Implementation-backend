# Test Cases

| | |
|---|---|
| System | TechValley Cloud Instance Monitoring System |
| Document | Test Case specification |
| Status | Baseline — matches the 125-case automated suite |
| Last reviewed | 2026-09-01 |

The test scenarios, conditions and data used to check the system for defects — each with
a precondition, the call to make, the data to send, and the exact result to expect.

**This document and [FUNCTIONAL_TESTS.md](FUNCTIONAL_TESTS.md) are not the same thing.**
That one describes the automated suite: how it is built, how it is isolated, what it
deliberately leaves out. This one is the case specification — what must be checked, in a
form that can be executed by hand against a running server or read as the acceptance
criteria for a requirement. The **Automated by** column links each case to the test that
runs it, and says so plainly where no test exists.

**Contents** — [1 Purpose](#1-purpose-and-scope) · [2 Environment](#2-test-environment) ·
[3 Baseline data](#3-baseline-test-data) · [4 Test cases](#4-test-cases) ·
[5 Cross-cutting cases](#5-cross-cutting-cases) · [6 Entry and exit criteria](#6-entry-and-exit-criteria) ·
[7 Defect handling](#7-defect-handling) · [8 Not covered](#8-what-these-cases-do-not-check) ·
[9 Traceability](#9-traceability-matrix)

---

## 1. Purpose and scope

These cases verify the functional requirements in
[../requirements/SRS.md § 4](../requirements/SRS.md#4-functional-requirements) and the
rules specified in [../requirements/FRS.md](../requirements/FRS.md). They cover:

- every endpoint's success path;
- every documented failure path, checking the **status code and the body shape**, because
  the API has two of them;
- every business rule whose behaviour is not obvious from the endpoint's name — the
  duplicate guard, the idempotent update, the `RUNNING` delete block, cost including
  stopped instances, detection covering more than the returned page.

They do **not** cover performance, concurrency or security; those are reviewed separately
and are listed in [§ 8](#8-what-these-cases-do-not-check).

### Case ID scheme

| Prefix | Area |
|---|---|
| `TC-AUTH` | Authentication and the token guard |
| `TC-INST` | Instance register and lifecycle |
| `TC-MON` | Monitoring scans and the report |
| `TC-ALRT` | Alert history and resolution |
| `TC-CLNT` | Clients, cost, forecast, SLA |
| `TC-DIAG` | Diagnosis endpoint |
| `TC-X` | Cross-cutting: pagination, scoping, error shapes |

### Priority

**P1** — a defect here breaks a documented guarantee or lets data cross a scope boundary.
**P2** — a defect here produces a wrong number or a wrong status code.
**P3** — a defect here is a usability or consistency problem.

---

## 2. Test environment

| Item | Value |
|---|---|
| Under test | The HTTP API — every case is a request in and a status code plus a JSON body out |
| Database | A fresh database seeded with the demo data. The automated suite builds one **per test** in memory; a manual run uses a `monitoring.db` deleted and recreated at startup |
| Authentication | Real. Every case obtains a token through `POST /api/auth/login` |
| External provider | Stubbed or absent. `TC-DIAG` cases assume no `ANTHROPIC_API_KEY` unless the case says otherwise |
| Clock | Server UTC. Relative seed timestamps (`72h ago`) are anchored to the moment the seed ran |

**Preconditions common to every case below**

1. The server is running and `GET /` answers `{"status": "ok", …}`.
2. The database has just been seeded and **no monitoring scan has run yet** — so the alert
   table is empty. Cases that need alerts create them in their own steps.
3. The tester holds tokens for all three demo accounts.

Running the automated equivalent: [RUNNING_TESTS.md](RUNNING_TESTS.md).

---

## 3. Baseline test data

Every expected value below is derived from the seed
([../demo/SEED_DATA.md](../demo/SEED_DATA.md)). If a change moves these numbers, the cases
move with it.

**Accounts** ([../demo/ACCOUNTS.md](../demo/ACCOUNTS.md))

| Alias | Email | Password | Role | Scope |
|---|---|---|---|---|
| `admin` | `admin@techvalley.vn` | `admin123!` | ADMIN | Everything |
| `manager1` | `lam@techvalley.vn` | `manager123!` | CLIENT_MANAGER | Clients 1–5, instances 1–9 |
| `manager2` | `minh@techvalley.vn` | `manager123!` | CLIENT_MANAGER | Clients 6–10, instances 10–15 |

**Estate**

| Fact | Value |
|---|---|
| Clients / instances | 10 / 15 |
| Status split | 10 RUNNING · 3 STOPPED · 2 ERROR |
| CPU ≥ 80 and RUNNING | instances `1` (91.5), `4` (85.2), `11` (88.4), `14` (96.3) |
| Just below the threshold | instance `10` at `78.9` — must **not** appear in warnings |
| ERROR | instances `5`, `9` |
| STOPPED ≥ 48h | instances `3`, `7`, `13` |
| Total monthly cost | `$2,100` — manager1 `$1,260`, manager2 `$840` |
| VinaSoft (client 1) | instances `1, 2, 3`; cost `$620`; forecast `$500` |
| Alerts after all three scans as ADMIN | 9 — 4 `CPU_HIGH`, 2 `ERROR_DETECTED`, 3 `LONG_STOPPED` |

---

## 4. Test cases

Column meanings: **Steps / data** is the call to make; **Expected** is the exact result;
**Automated by** is the test function that runs the case, or `—` where none does.

### 4.1 Authentication — TC-AUTH

| ID | Pri | Precondition | Steps / data | Expected | Automated by |
|---|:--:|---|---|---|---|
| **TC-AUTH-01** | P2 | Server running | `GET /` with no token | `200`, body `{"status":"ok","service":…,"docs":"/docs"}` | `health_check_is_public` |
| **TC-AUTH-02** | P1 | — | `POST /api/auth/login` `{"email":"admin@techvalley.vn","password":"admin123!"}` | `200`; `tokenType` = `bearer`; `role` = `ADMIN`; `name` = `TechValley Admin`; the JWT carries `sub`, `email`, `role`, `exp`; the token authorises a protected call | `login_returns_a_usable_token_with_role_and_name` |
| **TC-AUTH-03** | P2 | — | Log in as `lam@techvalley.vn` | `200`; `role` = `CLIENT_MANAGER`, `name` = `Thai Van Lam` — the response reflects the account, not a default | `login_issues_the_manager_role_for_a_manager_account` |
| **TC-AUTH-04** | P1 | — | (a) right email + wrong password; (b) unknown email + any password | Both `401` with **identical** body `{"detail":"Invalid email or password"}` — no account enumeration | `login_rejects_bad_credentials_without_revealing_which_part_failed` |
| **TC-AUTH-05** | P3 | — | `POST /api/auth/login` with `email` = `"not-an-email"` | `422`, before any database lookup | `login_rejects_a_malformed_email` |
| **TC-AUTH-06** | P1 | — | Call one endpoint per router with **no** `Authorization` header | Every one `401` `Not authenticated. Provide a Bearer token.` | `protected_endpoints_reject_a_missing_token` |
| **TC-AUTH-07** | P1 | — | Send (a) `Bearer garbage`; (b) a token signed with a different secret | Both `401 Invalid token` | `invalid_tokens_are_rejected` |
| **TC-AUTH-08** | P1 | — | Send a well-formed token whose `exp` is in the past | `401 Token has expired` | `expired_token_is_rejected` |
| **TC-AUTH-09** | P1 | A valid token for manager1 | Delete the member row, then call any endpoint with that token | `401 Member no longer exists` — the member is re-read on every request | `token_for_a_member_that_no_longer_exists_is_rejected` |

### 4.2 Instances — TC-INST

| ID | Pri | Precondition | Steps / data | Expected | Automated by |
|---|:--:|---|---|---|---|
| **TC-INST-01** | P1 | manager1 token | `POST /api/instances` `{"instanceName":"vinasoft-cache-01","region":"ap-southeast-1","instanceType":"MEDIUM","clientId":1}` | `201`; `monthlyCost` = `120.0`; `status` = `RUNNING`; `cpuUsage` = `0.0`; `launchedAt` and `updatedAt` set by the server | `create_instance_derives_cost_and_applies_defaults` |
| **TC-INST-02** | P1 | admin token | Register one instance of each type | `monthlyCost` = `50.0` / `120.0` / `250.0` for SMALL / MEDIUM / LARGE, regardless of any cost sent in the body | `create_instance_prices_every_type` |
| **TC-INST-03** | P1 | manager1 token | `POST /api/instances` with `clientId` = `6` (manager2's) | `403`; the instance is **not** created | `create_instance_is_blocked_for_another_managers_client` |
| **TC-INST-04** | P2 | admin token | `POST /api/instances` with `clientId` = `999` | `404` with body `{"error":"NotFound","detail":…}` | `create_instance_rejects_an_unknown_client` |
| **TC-INST-05** | P2 | admin token | `cpuUsage` = `150`; `instanceType` = `"HUGE"`; `instanceName` = `""` (three requests) | `422` on each | `create_instance_validates_the_body` |
| **TC-INST-06** | P2 | admin token | `GET /api/instances` | `200`; envelope with `total` = `15`, `page` = `1`, `size` = `10`, `totalPages` = `2`; 10 items | `list_instances_paginates` |
| **TC-INST-07** | P1 | manager tokens | `GET /api/instances` as manager1, then manager2 | `total` = `9` and `6`; the two sets are disjoint and sum to the ADMIN total | `list_instances_is_scoped_to_the_callers_clients` |
| **TC-INST-08** | P1 | manager1 token | `GET /api/instances?clientId=6` | `200` with an **empty** `items` and `total` = `0` — a filter narrows, never widens. Not `403` | `filtering_by_another_managers_client_returns_nothing` |
| **TC-INST-09** | P2 | admin token | `?status=RUNNING`; `?region=ap-northeast-2`; `?instanceType=LARGE`; `?clientId=1` | Each returns only matching rows, and `total` matches the seed counts | `list_instances_filters` |
| **TC-INST-10** | P2 | admin token | `?sort=-cpuUsage`; `?sort=instanceName`; `?sort=nonsense` | Descending by CPU; ascending by name; the unknown field **silently falls back to `id`** rather than erroring | `list_instances_sorts` |
| **TC-INST-11** | P1 | admin token | Walk every page of `?sort=status&size=4` and collect the ids | All 15 ids, each exactly once — no gap, no repeat, despite only three distinct sort values. This is what the `id` tiebreaker buys | `pages_partition_a_non_unique_sort_without_gaps_or_repeats` |
| **TC-INST-12** | P3 | admin token | `GET /api/instances?page=99` | `200` with empty `items` — **not** `404` | `list_instances_paginates` |
| **TC-INST-13** | P2 | admin token | `page=0`; `size=0`; `size=101`; `status=NOPE` | `422` on each | `list_instances_validates_query_parameters` |
| **TC-INST-14** | P2 | tokens for both managers | `GET /api/instances/1` as manager1, as manager2, and `GET /api/instances/999` | Full record with all ten fields; `403` across scope; `404` for the unknown id | `get_instance_returns_the_full_record`, `get_instance_enforces_scope_and_existence` |
| **TC-INST-15** | P1 | Instance 1 is RUNNING at 91.5 | `PATCH /api/instances/1/status` `{"status":"STOPPED"}` | `200`; `status` = `STOPPED`; `cpuUsage` forced to `0.0`; `updatedAt` has moved | `stopping_an_instance_resets_cpu_and_advances_updated_at` |
| **TC-INST-16** | P2 | Instance 2 RUNNING | `PATCH .../2/status` `{"status":"STOPPED","cpuUsage":25.5}` | `cpuUsage` = `25.5` — an explicit value beats the reset; `monthlyCost` unchanged | `status_update_keeps_an_explicit_cpu_value` |
| **TC-INST-17** | P1 | Instance 3 is STOPPED at 0.0 | Send `{"status":"STOPPED"}`, note `updatedAt`, send the identical request again | Both `200`; **`updatedAt` is identical** — the no-op must not restart the 48-hour clock | `status_change_is_scoped_and_idempotent` |
| **TC-INST-18** | P2 | manager1 token | (a) `cpuUsage` = `150`; (b) `status` = `"BROKEN"`; (c) body without `status`; (d) `PATCH` instance `10` (manager2's) | (a)–(c) `422`; (d) `403` | `status_update_validates_its_body`, `status_change_is_scoped_and_idempotent` |
| **TC-INST-19** | P1 | Instance 1 is RUNNING | `DELETE /api/instances/1` | `409`; body `{"error":"ActiveInstanceException","detail":"Instance 1 is RUNNING and cannot be deleted. Stop it first."}`; the row still exists | `running_instance_cannot_be_deleted` |
| **TC-INST-20** | P1 | Instance 1 stopped first | `DELETE /api/instances/1`, then `GET /api/instances/1` | `204` with an empty body, then `404` | `instance_is_deleted_once_stopped` |
| **TC-INST-21** | P1 | A scan has recorded alerts for instance 1 | Stop and delete instance 1, then `GET /api/alerts` | No alert references instance 1 — the cascade fired | `deleting_an_instance_removes_its_alerts`, `deleting_an_instance_removes_its_alerts_from_the_history` |
| **TC-INST-22** | P1 | Instance 13 is STOPPED and belongs to manager2 | `DELETE /api/instances/13` as manager1 | `403`, and the row survives — the scope check runs **before** the delete | `delete_enforces_scope_and_existence` |

### 4.3 Monitoring — TC-MON

| ID | Pri | Precondition | Steps / data | Expected | Automated by |
|---|:--:|---|---|---|---|
| **TC-MON-01** | P1 | Freshly seeded, no scan yet | `GET /api/monitor/warnings` as admin | `200`; instances `[1, 4, 11, 14]`; instance `10` (78.9%) absent; 4 `CPU_HIGH` alerts now exist, each message carrying the reading | `warnings_are_scoped_auto_recorded_and_deduplicated` |
| **TC-MON-02** | P1 | TC-MON-01 has run | Call `GET /api/monitor/warnings` again | Same four instances; the `CPU_HIGH` alert count is **still 4** — the duplicate guard held | `warnings_are_scoped_auto_recorded_and_deduplicated` |
| **TC-MON-03** | P1 | One `CPU_HIGH` alert resolved, CPU still high | Resolve alert, then scan warnings again | A **new** `CPU_HIGH` alert is opened for that instance — resolution re-arms detection | `warnings_are_scoped_auto_recorded_and_deduplicated` |
| **TC-MON-04** | P1 | Freshly seeded | `GET /api/monitor/errors` twice | Instances `[5, 9]` both times; 2 `ERROR_DETECTED` alerts after the first call and still 2 after the second; messages start `[CRITICAL]` | `error_and_long_stopped_monitoring_auto_record_without_duplicates` |
| **TC-MON-05** | P1 | Freshly seeded | `GET /api/monitor/long-stopped` twice | Instances `[3, 7, 13]` both times; 3 `LONG_STOPPED` alerts, no duplicates | `error_and_long_stopped_monitoring_auto_record_without_duplicates` |
| **TC-MON-06** | P1 | manager tokens | Run all three scans as manager1, then as manager2 | manager1 sees warnings `[1, 4]`, errors `[5, 9]`, idle `[3, 7]`; manager2 sees `[11, 14]`, `[]`, `[13]`. No alert is created for the other manager's instances | `warnings_are_scoped_auto_recorded_and_deduplicated`, `full_report_and_manager_scope` |
| **TC-MON-07** | P1 | Freshly seeded | `GET /api/monitor/warnings?size=1` | `items` has **one** instance, `total` = `4`, and **four** `CPU_HIGH` alerts are recorded. Pagination bounds the response, never the detection | `a_scan_records_alerts_for_every_match_not_only_the_page` |
| **TC-MON-08** | P2 | Freshly seeded | Walk `GET /api/monitor/warnings?size=2` page 1 then page 2 | `[1, 4]` then `[11, 14]` — the whole match set, each instance once | `monitoring_pages_partition_the_matches` |
| **TC-MON-09** | P2 | — | (a) `size=101` on each of the three scans; (b) run the scans with `ID_BATCH_SIZE` set to 1 and 3 | (a) `422` each; (b) identical instances, identical alert counts, identical dedup outcome as at the default — the batching is not observable | `monitoring_rejects_out_of_range_paging`, `monitoring_scans_are_unchanged_by_the_batch_size` |
| **TC-MON-10** | P1 | Freshly seeded, all three scans run as admin | `GET /api/monitor/report` | `instanceCountByStatus` = `{RUNNING:10, STOPPED:3, ERROR:2}`; `warningCount` = `4`; `totalMonthlyCost` = `2100.0`; `unresolvedAlertCount` = `9`; `unresolvedAlerts` newest first | `full_report_and_manager_scope` |
| **TC-MON-11** | P1 | Same, per manager | Read the report as manager1 and manager2 | `$1,260` and `$840`, summing to the ADMIN `$2,100`; each sees only their own alerts | `full_report_and_manager_scope` |
| **TC-MON-12** | P2 | 29 unresolved alerts exist | `GET /api/monitor/report` | `unresolvedAlertCount` = `29`, `unresolvedAlerts` has exactly `20` entries, newest first | `report_caps_the_embedded_alerts_but_not_the_count` |
| **TC-MON-13** | P2 | — | Report with all three statuses absent from a manager's scope | `instanceCountByStatus` still contains all three keys, zero-filled | `full_report_and_manager_scope` |
| **TC-MON-14** | P2 | — | Call the four monitoring routes and the status `PATCH` with no token | `401` on every one | `member_c_endpoints_require_authentication` |
| **TC-MON-15** | P2 | Freshly seeded | `GET /api/monitor/report`, then `GET /api/alerts` | The report created **no** alerts — the history is still empty | `alert_history_is_empty_before_the_first_scan` |

### 4.4 Alerts — TC-ALRT

| ID | Pri | Precondition | Steps / data | Expected | Automated by |
|---|:--:|---|---|---|---|
| **TC-ALRT-01** | P2 | Freshly seeded, no scan | `GET /api/alerts` | `total` = `0` — alerts come from detection, never from the seed | `alert_history_is_empty_before_the_first_scan` |
| **TC-ALRT-02** | P1 | All three scans run as admin | `GET /api/alerts?size=50` | 9 alerts, ordered `detectedAt` descending, all `isResolved` = `false`, all `resolvedAt` = `null` | `alert_history_returns_every_detection_newest_first` |
| **TC-ALRT-03** | P3 | Same | Read the message of the alert for instance 1 and instance 14 | Messages embed the real readings — `91.5%` and `96.3%` | `alert_history_carries_the_detection_message` |
| **TC-ALRT-04** | P2 | Same | `?alertType=CPU_HIGH`, `=ERROR_DETECTED`, `=LONG_STOPPED` | Instances `{1,4,11,14}`, `{5,9}`, `{3,7,13}` | `alert_history_filters_by_type` |
| **TC-ALRT-05** | P2 | One alert resolved | `?isResolved=true` and `?isResolved=false` | The two results partition the nine alerts | `alert_history_filters_by_resolved_state` |
| **TC-ALRT-06** | P2 | Same | `?dateFrom=<today>`; `?dateTo=<today>`; `?dateFrom=<tomorrow>` | The first two return all of today's alerts (both bounds inclusive, whole day); the third returns none | `alert_history_filters_by_detection_date` |
| **TC-ALRT-07** | P2 | Same | `alertType=NOPE`; `dateFrom=21-08-2026`; `isResolved=maybe` | `422` on each | `alert_history_validates_query_parameters` |
| **TC-ALRT-08** | P1 | Both managers have scanned | `GET /api/alerts` as manager1, then manager2 | manager1 sees alerts for instances `{1,3,4,5,7,9}`; manager2 `{11,13,14}` | `alert_history_is_scoped_to_the_callers_clients` |
| **TC-ALRT-09** | P2 | An unresolved alert exists | `GET /api/alerts?size=4` and walk all pages | Page sizes `4 / 4 / 1`; `total` stays `9` on every page | `alert_history_is_paginated` |
| **TC-ALRT-10** | P1 | Nine alerts from one scan, all sharing `detectedAt` | Walk every page and collect ids | Each alert exactly once — this passes **only** because `id` breaks the `detectedAt` tie | `alert_pages_partition_the_history_without_gaps_or_repeats` |
| **TC-ALRT-11** | P3 | Same | `GET /api/alerts?page=99` | `200` with empty `items` | `alert_history_page_past_the_end_is_empty_not_404` |
| **TC-ALRT-12** | P2 | Same | `page=0`; `size=0`; `size=101` | `422` on each | `alert_history_rejects_out_of_range_paging` |
| **TC-ALRT-13** | P1 | manager1 has scanned | `GET /api/alerts?alertType=CPU_HIGH` as manager1 | `total` = `2`, not `4` — the count is scoped **and** filtered | `alert_pagination_applies_after_filtering_and_scoping` |
| **TC-ALRT-14** | P1 | An unresolved alert | `PATCH /api/alerts/{id}/resolve`, note `resolvedAt`, call it again | Both `200`; `isResolved` = `true`; **`resolvedAt` identical** on the second call | `resolving_an_alert_stamps_it_once` |
| **TC-ALRT-15** | P2 | Nine unresolved alerts | Resolve one, then read the report | `unresolvedAlertCount` drops from `9` to `8` | `resolving_removes_the_alert_from_the_report` |
| **TC-ALRT-16** | P1 | An alert on manager2's instance | Resolve it as manager1 | `403`, and the alert is still unresolved | `resolving_another_managers_alert_is_forbidden` |
| **TC-ALRT-17** | P3 | — | `PATCH /api/alerts/9999/resolve` | `404` with body `{"detail": …}` and **no `error` key** — the documented shape inconsistency | `resolving_an_unknown_alert_is_404` |

### 4.5 Clients, cost and SLA — TC-CLNT

| ID | Pri | Precondition | Steps / data | Expected | Automated by |
|---|:--:|---|---|---|---|
| **TC-CLNT-01** | P1 | admin token | `POST /api/clients` `{"clientName":"NewCo","contractPlan":"PREMIUM","managerId":2}` | `201`; the client appears immediately in manager1's own listing | `admin_registers_a_client` |
| **TC-CLNT-02** | P1 | manager1 token | The same `POST` | `403 ADMIN role required`; nothing written | `client_registration_is_admin_only` |
| **TC-CLNT-03** | P2 | admin token | `managerId` = `1` (the administrator) | `400` with `{"error":"ValidationError", …}` | `client_registration_rejects_a_manager_id_that_is_not_a_manager` |
| **TC-CLNT-04** | P2 | admin token | `managerId` = `999` | `404` with `{"error":"NotFound", …}` | `client_registration_rejects_an_unknown_manager_id` |
| **TC-CLNT-05** | P2 | admin token | `contractPlan` = `"GOLD"`; `clientName` = `""`; `managerId` = `"two"` | `422` on each | `client_registration_validates_the_body` |
| **TC-CLNT-06** | P1 | All three tokens | `GET /api/clients` | admin `10`; manager1 clients `1–5`; manager2 clients `6–10` | `client_list_is_scoped_by_role` |
| **TC-CLNT-07** | P1 | manager1 token | `GET /api/clients?size=4` | Items `[1–4]` then `[5]`; **`total` = `5`, not `10`** — the envelope never leaks the table size | `client_list_is_paginated`, `client_list_pagination_counts_only_the_callers_clients` |
| **TC-CLNT-08** | P2 | manager1 token | `GET /api/clients/1/instances` | Instances `[1, 2, 3]`, ordered by id | `client_instances_are_listed_for_the_owning_manager` |
| **TC-CLNT-09** | P2 | manager1 token | `GET /api/clients/1/instances?size=2` | `[1, 2]` then `[3]`; `total` = `3` | `client_instances_are_paginated` |
| **TC-CLNT-10** | P1 | manager1 token | All four sub-resources (`/instances`, `/cost`, `/cost-forecast`, `/sla`) for client `6`, and for client `999` | `403` across scope; `404` for the unknown client | `client_sub_resources_enforce_scope_and_existence` |
| **TC-CLNT-11** | P1 | manager1 token | `GET /api/clients/1/cost` | `month` = current `YYYY-MM`; `instanceCount` = `3`; `totalMonthlyCost` = `620.0` **including the STOPPED instance**; `costByInstance` has 3 rows, each with its `status` | `current_cost_sums_every_instance_regardless_of_status` |
| **TC-CLNT-12** | P2 | Same | Register a SMALL instance for client 1, re-read the cost | The total rises by exactly `$50` | `current_cost_follows_a_newly_registered_instance` |
| **TC-CLNT-13** | P1 | Same | Call `/cost` and `/sla` for client 1 with `?size=1` in the query | `costByInstance` and `instanceDetails` still have **3** rows — the page bound must not leak into the arithmetic | `cost_and_sla_still_cover_every_instance_not_a_page` |
| **TC-CLNT-14** | P1 | manager1 token | `GET /api/clients/1/cost-forecast` | `forecastMonth` = next month; `runningInstanceCount` = `2`; `forecastCost` = `500.0`; `breakdown` = `{"LARGE":{count:2, unitPrice:250.0, subtotal:500.0}}` — the STOPPED instance is excluded and `MEDIUM` is **absent**, not zero | `forecast_counts_only_running_instances` |
| **TC-CLNT-15** | P2 | Same | Start instance 3 (`RUNNING`), re-read the forecast | Rises to `$620` and gains a `MEDIUM` entry | `forecast_reacts_to_a_status_change` |
| **TC-CLNT-16** | P2 | A client with nothing running | `GET /api/clients/{id}/cost-forecast` | `forecastCost` = `0.0`, `breakdown` = `{}` — not an error | `forecast_of_a_client_without_running_instances_is_zero` |
| **TC-CLNT-17** | P3 | System clock in December | Read a forecast | `forecastMonth` rolls the year — `2026-12` → `2027-01` | **Manual** — needs a clock change; the rule is specified in [FRS § F-CLNT-05](../requirements/FRS.md#f-clnt-05--next-month-cost-forecast) |
| **TC-CLNT-18** | P1 | Client 4 (STANDARD), instance RUNNING | `GET /api/clients/4/sla` | `slaThreshold` = `99.0`; `uptimePercent` = `100.0`; `isViolation` = `false` | `sla_reports_full_uptime_when_every_instance_is_running` |
| **TC-CLNT-19** | P1 | Client 3 (BASIC) has a long-stopped instance | `GET /api/clients/3/sla` | `slaThreshold` = `95.0`; `isViolation` = `true`; per-instance `runningHours` < `measuredHours` for the stopped instance and equal for the running one | `sla_flags_a_violation_for_a_long_stopped_instance` |
| **TC-CLNT-20** | P2 | A client with no instances | `GET /api/clients/{id}/sla` | `uptimePercent` = `100.0`, `isViolation` = `false`, empty `instanceDetails` — not `0%` | `sla_of_a_client_without_instances_is_not_a_violation` |
| **TC-CLNT-21** | P2 | Any client with instances | Recompute `runningHours / measuredHours` from `instanceDetails` | Each equals the reported per-instance `uptimePercent` (3 decimals), and their mean equals the client figure — the response is auditable | `sla_flags_a_violation_for_a_long_stopped_instance` |
| **TC-CLNT-22** | P3 | An instance launched earlier today | Read its client's SLA | `measuredHours` counts from `launchedAt`, not from the first of the month | **Manual** — depends on wall-clock time; see [§ 8](#8-what-these-cases-do-not-check) |

### 4.6 Diagnosis — TC-DIAG

| ID | Pri | Precondition | Steps / data | Expected | Automated by |
|---|:--:|---|---|---|---|
| **TC-DIAG-01** | P1 | **No** `ANTHROPIC_API_KEY` | `GET /api/instances/5/diagnosis` | `200`; `source` = `"rule-based"`; `diagnosis` contains *Probable Causes*, *Recommended Actions*, *Prevention* | `diagnosis_falls_back_to_a_rule_based_answer` |
| **TC-DIAG-02** | P1 | Provider available | Same call | `200`; `source` = `"llm"`; the model's text returned verbatim | `diagnosis_uses_the_model_answer_when_one_is_available` |
| **TC-DIAG-03** | P2 | Instance with alerts | Same call | The prompt carries that instance and **its** alerts — not another instance's | `diagnosis_is_given_the_instance_and_its_recent_alerts` |
| **TC-DIAG-04** | P1 | Provider raises an exception | Same call | `200` with a rule-based answer — **never** a `5xx` | `diagnosis_survives_a_provider_failure` |
| **TC-DIAG-05** | P2 | Stubbed provider returning mixed content blocks | Same call | Text blocks are returned; thinking blocks are dropped | `diagnosis_returns_the_text_the_provider_produced` |
| **TC-DIAG-06** | P3 | A healthy RUNNING instance | `GET /api/instances/2/diagnosis` | `200` with a diagnosis — the endpoint is not restricted to ERROR instances | `diagnosis_works_for_a_healthy_instance_too` |
| **TC-DIAG-07** | P1 | manager1 token | Diagnose instance `10` (manager2's), then instance `999` | `403`, then `404` | `diagnosis_enforces_scope_and_existence` |
| **TC-DIAG-08** | P2 | Provider that never answers | Same call | The response arrives within about a minute (30 s timeout, one retry) with `source` = `"rule-based"` | **Manual** — a timing property; specified in [SRS § NFR-PERF-04](../requirements/SRS.md#52-performance) |

---

## 5. Cross-cutting cases

These hold on **every** endpoint of their class. They are listed once rather than repeated
per endpoint, and each is exercised inside the suites above.

| ID | Pri | Applies to | Check | Expected | Automated by |
|---|:--:|---|---|---|---|
| **TC-X-01** | P2 | All 7 list endpoints | Send `page`/`size` | Same envelope everywhere: `items`, `total`, `page`, `size`, `totalPages` | `list_instances_paginates`, `alert_history_is_paginated`, `client_list_is_paginated`, `client_instances_are_paginated`, `monitoring_pages_partition_the_matches` |
| **TC-X-02** | P1 | All 7 list endpoints | `size=101`, `page=0`, `size=0` | `422` everywhere — the cap lives in one module and cannot differ per route | `list_instances_validates_query_parameters`, `alert_history_rejects_out_of_range_paging`, `monitoring_rejects_out_of_range_paging` |
| **TC-X-03** | P1 | All list endpoints | Compare `total` for a manager against the ADMIN total | The manager's count covers their scope only | `client_list_pagination_counts_only_the_callers_clients`, `alert_pagination_applies_after_filtering_and_scoping` |
| **TC-X-04** | P1 | All single-resource endpoints | Request another manager's resource | `403` — **not** `404`; the resource is confirmed to exist ([AUTHORIZATION § 3](../business-rules/AUTHORIZATION.md#3-403-rather-than-404)) | `get_instance_enforces_scope_and_existence`, `client_sub_resources_enforce_scope_and_existence`, `resolving_another_managers_alert_is_forbidden` |
| **TC-X-05** | P2 | Domain failures | Trigger `409`, `404` on an instance/client, `400` on a client | Body is `{"error": …, "detail": …}` | `running_instance_cannot_be_deleted`, `create_instance_rejects_an_unknown_client`, `client_registration_rejects_a_manager_id_that_is_not_a_manager` |
| **TC-X-06** | P3 | Auth and alert `404` | Trigger a `401`, a `403`, an unknown alert id | Body is `{"detail": …}` with no `error` key | `resolving_an_unknown_alert_is_404`, `protected_endpoints_reject_a_missing_token` |
| **TC-X-07** | P2 | Every response | Inspect field names and datetime format | camelCase throughout; ISO-8601 UTC such as `2026-08-21T14:07:00` | Asserted implicitly by every case above |
| **TC-X-08** | P1 | All 7 list endpoints, plus the report | Log in as a `CLIENT_MANAGER` with **no** clients assigned and call each one | Every response is empty — `total` = `0`, `items` = `[]`, and the report all zeros. An empty scope matches nothing; it must never fall back to matching everything | `a_manager_with_no_clients_sees_nothing` |

---

## 6. Entry and exit criteria

**Entry** — the suite may be run when the application starts, `GET /` answers, and the
database is freshly seeded.

**Exit** — a change is releasable when:

1. Every P1 case passes. A P1 failure is a release blocker.
2. Every P2 case passes, or the failure is recorded as a known defect with a decision.
3. `pytest -q` reports **125 passed**.
4. Any case whose expected value the change moved has been updated **in the same commit**,
   along with [../demo/SEED_DATA.md](../demo/SEED_DATA.md) and
   [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) if the numbers there moved
   ([../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md)).
5. If a response, status code or seed number changed, the affected Swagger captures have
   been re-taken ([../screenshots/README.md](../screenshots/README.md)).

**Regression set** — the fastest meaningful subset for a small change is TC-AUTH-02,
TC-INST-01, TC-INST-17, TC-INST-19, TC-MON-01, TC-MON-02, TC-MON-07, TC-ALRT-14,
TC-CLNT-11, TC-CLNT-14, TC-DIAG-01. Those eleven cover one guarantee each that nothing
else would catch.

---

## 7. Defect handling

| Step | Action |
|---|---|
| 1 | Reproduce through the API, not through a service call — these cases specify observable behaviour |
| 2 | Decide whether the **code** or the **case** is wrong. A case is wrong when a rule changed deliberately; then it and its rule document move together |
| 3 | Fix the code, and add the case that would have caught it — [FUNCTIONAL_TESTS § 8](FUNCTIONAL_TESTS.md#8-adding-a-test) |
| 4 | Record it in [../changelog/CHANGELOG.md](../changelog/CHANGELOG.md) with its commit |

Performance and security findings follow their own registers rather than this document:
[../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) and
[../security/SECURITY_BUGS.md](../security/SECURITY_BUGS.md).

---

## 8. What these cases do not check

Stated so no reader takes a green run as broader assurance than it is.

| Not checked | Why, and where it is covered instead |
|---|---|
| Exact SLA percentages for partially-stopped instances | They depend on the wall clock and the day of the month. The cases assert the **decision** (`isViolation`) and the internal consistency of the response instead — [SLA § 3](../business-rules/SLA.md) |
| Concurrency and races | Single-process SQLite; the dedup check is read-then-write and is not exercised under parallel calls |
| Latency, throughput, connection-pool behaviour | Measured separately — [PERFORMANCE_BUGS](../performance/PERFORMANCE_BUGS.md) |
| Token forgery, disclosure, injection | Reviewed separately — [SECURITY_BUGS](../security/SECURITY_BUGS.md). **A green suite verifies none of the security NFRs** |
| The real Anthropic API | Needs credentials and returns non-deterministic text — the provider is the only stub in the suite |
| `cost_snapshots` | Seeded but read by no endpoint, so there is nothing observable to assert |
| Token expiry over real elapsed time | Simulated by signing a token with a past `exp` rather than waiting two hours |

---

## 9. Traceability matrix

Requirement → the cases that verify it. Business-level traceability continues in
[../requirements/BRD.md § 12](../requirements/BRD.md#12-traceability).

| Requirement | Function | Test cases |
|---|---|---|
| FR-01 Authentication | F-AUTH-01, F-AUTH-02, F-AUTH-03 | TC-AUTH-01 … TC-AUTH-09 |
| FR-02 Client management | F-CLNT-01, F-CLNT-02, F-CLNT-03 | TC-CLNT-01 … TC-CLNT-10 |
| FR-03 Instance register | F-INST-01, F-INST-02, F-INST-03 | TC-INST-01 … TC-INST-14 |
| FR-04 Instance lifecycle | F-INST-04, F-INST-05 | TC-INST-15 … TC-INST-22 |
| FR-05 Detection and reporting | F-MON-01 … F-MON-04 | TC-MON-01 … TC-MON-15 |
| FR-06 Alert lifecycle | F-ALRT-01, F-ALRT-02 | TC-ALRT-01 … TC-ALRT-17 |
| FR-07 Cost and forecast | F-CLNT-04, F-CLNT-05 | TC-CLNT-11 … TC-CLNT-17 |
| FR-08 SLA reporting | F-CLNT-06 | TC-CLNT-18 … TC-CLNT-22 |
| FR-09 Diagnosis | F-DIAG-01 | TC-DIAG-01 … TC-DIAG-08 |
| FR-10 Cross-cutting | F-X-01, F-X-02, F-X-03 | TC-X-01 … TC-X-08 |
| NFR-REL-01 Provider never fails a request | F-DIAG-01 | TC-DIAG-01, TC-DIAG-04 |
| NFR-REL-04 Repeated writes are no-ops | F-INST-04, F-ALRT-02 | TC-INST-17, TC-ALRT-14 |
| NFR-REL-05 No orphaned alerts | F-INST-05 | TC-INST-21 |
| NFR-REL-06 Pages partition exactly | F-X-01 | TC-INST-11, TC-ALRT-10, TC-MON-08 |
| NFR-SEC-02 Authorization per request | F-X-02 | TC-AUTH-09, TC-X-03, TC-X-04, TC-X-08 |
| NFR-SEC-03 No account enumeration | F-AUTH-01 | TC-AUTH-04 |
| NFR-USE-04 Over-range page is empty | F-X-01 | TC-INST-12, TC-ALRT-11 |

Requirements marked **D** in [SRS § 5](../requirements/SRS.md#5-non-functional-requirements)
— the performance NFRs and NFR-SEC-01/04/05/06 — have **no** row here on purpose: they are
verified by a measurement or a review, not by these cases.

---

## 10. Related

| Document | Why |
|---|---|
| [FUNCTIONAL_TESTS.md](FUNCTIONAL_TESTS.md) | How the automated suite that runs these cases is built and isolated |
| [RUNNING_TESTS.md](RUNNING_TESTS.md) | Installing, running, selecting a case, reading a failure |
| [../requirements/FRS.md](../requirements/FRS.md) | The rule each case is checking |
| [../requirements/USE_CASES.md](../requirements/USE_CASES.md) | The same flows as scenarios, with acceptance criteria |
| [../demo/SEED_DATA.md](../demo/SEED_DATA.md) | The baseline every expected value comes from |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | A manual run through most of these cases in order |
| [../api/ERRORS.md](../api/ERRORS.md) | The two error body shapes the negative cases assert |
