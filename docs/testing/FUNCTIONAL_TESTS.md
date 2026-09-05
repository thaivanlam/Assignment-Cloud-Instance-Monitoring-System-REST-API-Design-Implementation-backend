# Functional Tests

What the automated suite verifies, how it is built, and what it deliberately leaves out.
The tests live in [../../tests/](../../tests/). To run them, see
[RUNNING_TESTS.md](RUNNING_TESTS.md).

---

## 1. What "functional" means here

Every test drives the API the way a client does: an HTTP request in, a status code and a
JSON body out. Nothing calls a service function directly to assert on its return value.

| Layer | In the test |
|---|---|
| HTTP + routing + validation | Real — requests go through FastAPI via `TestClient` |
| Controllers, services, auth | Real — no mocks |
| Database | Real SQLAlchemy against in-memory SQLite, seeded with the demo data |
| Anthropic provider | **Stubbed** — see [section 6](#6-the-only-stub-the-llm-provider) |

The consequence worth stating: a test failing here means the **observable behaviour** of
an endpoint changed. It does not tell you which internal function changed, and that is
intentional — the suite exists to protect the contract documented in
[../api/ENDPOINTS.md](../api/ENDPOINTS.md) and the rules in
[../business-rules/](../business-rules/README.md), not the shape of the code behind it.

---

## 2. Isolation: one database per test

[../../tests/conftest.py](../../tests/conftest.py) provides two fixtures.

**`api`** builds a fresh in-memory SQLite database for every single test, creates the
schema, runs [app/seed.py](../../app/seed.py) against it, and overrides the `get_db`
dependency so the application uses that database. It yields `(client, db)` — the HTTP
client and the same session, so a test can assert against the database directly after a
request:

```python
def test_instance_is_deleted_once_stopped(api, auth_headers):
    client, db = api
    ...
    assert db.get(Instance, 1) is None
```

Four details make this work:

- `StaticPool` keeps one connection alive, so pytest and FastAPI's worker thread see the
  same in-memory database. Without it, each connection would get its own empty database.
- The session factory carries the same arguments as the application's — including
  `expire_on_commit=False` — so the suite exercises the session semantics the API
  actually runs on rather than SQLAlchemy's defaults
  ([../design/DATABASE.md § 3](../design/DATABASE.md#3-the-session-factory)).
- The override is cleared and the schema dropped in the fixture teardown, so no state
  leaks between tests. Tests may create, mutate, and delete freely, and they may run in
  any order.
- The engine is **disposed** in teardown. `StaticPool` holds its connection — and with
  it the in-memory database — until disposal, so skipping this leaves one live database
  per test behind and the suite slows down as it runs.

**`auth_headers`** logs in as all three demo accounts through `POST /api/auth/login` and
returns ready-made `Authorization` headers keyed `admin`, `manager1`, `manager2`.

**`memoised_seed_hashing`** is session-scoped and autouse. Seeding runs once per test and
hashes three demo passwords at 260,000 PBKDF2 iterations; memoising it for the session
cuts the suite's runtime by roughly two thirds. Only the seed is memoised — every login
still verifies its password for real.

Why the fixture builds its own engine at all, and what an in-memory database gives up
compared with the file the application runs on:
[../design/DATABASE.md](../design/DATABASE.md).

The real `monitoring.db` file is never opened: the `get_db` override redirects every
session, and the startup lifespan that would seed it does not run under `TestClient`.

---

## 3. The baseline every assertion is written against

The seed is fixed data, so expected values can be exact rather than approximate. These
are the facts the assertions depend on — full detail in
[../demo/SEED_DATA.md](../demo/SEED_DATA.md).

| Fact | Value |
|---|---|
| Members | `1` ADMIN, `2` manager1 (`lam@`), `3` manager2 (`minh@`) |
| Clients | `1–5` belong to manager1, `6–10` to manager2 |
| Instances | `1–9` under manager1's clients, `10–15` under manager2's |
| Status split | 10 RUNNING · 3 STOPPED · 2 ERROR |
| Total monthly cost | `$2,100` — manager1 `$1,260`, manager2 `$840` |
| CPU ≥ 80% and RUNNING | instances `1`, `4`, `11`, `14` |
| ERROR | instances `5`, `9` |
| STOPPED ≥ 48h | instances `3`, `7`, `13` |
| Alerts | **none** — the seed records no alerts; they only appear after a monitoring scan |

If a change to `app/seed.py` moves any of these numbers, the suite fails loudly. That is
the intended coupling: [../demo/SEED_DATA.md](../demo/SEED_DATA.md) and
[../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) quote the same figures, and the tests
are what keeps those documents honest.

---

## 4. The suites

128 cases across six files. Each file covers one area of the API.

### 4.1 `test_auth.py` — health check and the JWT guard (19 cases)

| Case | Pins |
|---|---|
| `health_check_is_public` | `GET /` answers without a token |
| `login_returns_a_usable_token_with_role_and_name` | Claims (`sub`, `email`, `role`, `exp`) are correct **and** the token authorises a real call |
| `login_issues_the_manager_role_for_a_manager_account` | `role`/`name` reflect the account, not a default |
| `login_rejects_bad_credentials_without_revealing_which_part_failed` | Wrong password and unknown email give the *same* `401` body — no account enumeration |
| `login_rejects_a_malformed_email` | `422` from schema validation |
| `protected_endpoints_reject_a_missing_token` | Nine endpoints, one per router, all `401` |
| `invalid_tokens_are_rejected` | Garbage and foreign-secret tokens both `401 Invalid token` |
| `expired_token_is_rejected` | `401 Token has expired` |
| `token_for_a_member_that_no_longer_exists_is_rejected` | `401 Member no longer exists` |

Rules: [../api/AUTHENTICATION.md](../api/AUTHENTICATION.md),
[../api/ERRORS.md](../api/ERRORS.md) §2.2.

### 4.2 `test_instances.py` — instance lifecycle and list conventions (38 cases)

| Case | Pins |
|---|---|
| `create_instance_derives_cost_and_applies_defaults` | `monthlyCost` comes from the type, never the request; defaults are `RUNNING` / `0.0` |
| `create_instance_prices_every_type` | SMALL `$50`, MEDIUM `$120`, LARGE `$250` |
| `create_instance_is_blocked_for_another_managers_client` | `403`, and nothing is written |
| `create_instance_rejects_an_unknown_client` | `404` with the `{error, detail}` body |
| `create_instance_validates_the_body` | CPU out of range, unknown enums, empty name → `422` |
| `list_instances_paginates` | `total` / `page` / `size` / `totalPages`, and a page past the end is an empty page, not an error |
| `list_instances_filters` | `status`, `region`, `instanceType`, `clientId`, and two filters combined |
| `list_instances_sorts` | `-cpuUsage` descending, `instanceName` ascending, unknown field falls back to `id` instead of failing |
| `list_instances_validates_query_parameters` | `page=0`, `size=0`, `size=101`, bad enums → `422` |
| `pages_partition_a_non_unique_sort_without_gaps_or_repeats` | Walking `sort=status` — three distinct values across 15 rows, so nearly every row is tied — visits each row exactly once. This is what the `id` tiebreaker buys |
| `list_instances_is_scoped_to_the_callers_clients` | manager1 sees 9, manager2 sees 6 |
| `filtering_by_another_managers_client_returns_nothing` | `clientId` cannot be used to read across the scope boundary — empty result, not `403` |
| `get_instance_returns_the_full_record` | Every field of `InstanceOut` |
| `get_instance_enforces_scope_and_existence` | `403` vs `404` |
| `stopping_an_instance_resets_cpu_and_advances_updated_at` | CPU is forced to `0.0`; `updatedAt` moves |
| `status_update_keeps_an_explicit_cpu_value` | A supplied `cpuUsage` survives; `monthlyCost` is untouched |
| `status_update_validates_its_body` | Out-of-range CPU, unknown status, missing status → `422` |
| `running_instance_cannot_be_deleted` | `409 ActiveInstanceException`, exact detail message, row still present |
| `instance_is_deleted_once_stopped` | `204` with an empty body, then `404` |
| `deleting_an_instance_removes_its_alerts` | The alert cascade actually fires |
| `delete_enforces_scope_and_existence` | `403` on another manager's STOPPED instance — the scope check runs before the delete |
| `a_manager_with_no_clients_reaches_no_single_instance` | An empty scope forbids all four single-object endpoints. The guard asks the database whether the instance's client is in scope ([../performance/PERFORMANCE_BUGS.md § PERF-11](../performance/PERFORMANCE_BUGS.md#perf-11)), and a caller who owns nothing is where such a check is easiest to lose |

Rules: [../business-rules/INSTANCE_LIFECYCLE.md](../business-rules/INSTANCE_LIFECYCLE.md),
[../api/CONVENTIONS.md](../api/CONVENTIONS.md),
[../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md).

### 4.3 `test_member_c.py` — monitoring scans and the report (12 cases)

| Case | Pins |
|---|---|
| `member_c_endpoints_require_authentication` | All four `/api/monitor/*` routes plus the status PATCH reject anonymous callers |
| `status_change_is_scoped_and_idempotent` | A repeated identical PATCH does **not** move `updatedAt` — the 48-hour STOPPED clock is not restarted |
| `warnings_are_scoped_auto_recorded_and_deduplicated` | Scanning twice records one alert; resolving one lets the next scan record a fresh alert |
| `error_and_long_stopped_monitoring_auto_record_without_duplicates` | ERROR `[5, 9]`, long-stopped `[3, 7, 13]`, no duplicates on rescan |
| `full_report_and_manager_scope` | Exact counts, `$2,100` / `$1,260` totals, unresolved alert lists per role |
| `a_scan_records_alerts_for_every_match_not_only_the_page` | **The rule pagination could most easily have broken.** `size=1` returns one instance and still records all four alerts |
| `monitoring_pages_partition_the_matches` | Walking `size=2` yields `[1, 4, 11, 14]` — the whole match set, once each |
| `monitoring_scans_are_unchanged_by_the_batch_size` | Same instances, same alert counts and same dedup outcome at `ID_BATCH_SIZE` 1 and 3 as at the default 500 — the batching is not observable |
| `monitoring_rejects_out_of_range_paging` | `size=101` → `422` on all three scans |
| `report_caps_the_embedded_alerts_but_not_the_count` | 29 unresolved alerts: `unresolvedAlertCount` is 29, `unresolvedAlerts` is the 20 newest |

Rules: [../business-rules/ALERTING.md](../business-rules/ALERTING.md),
[../team/MEMBER_C.md](../team/MEMBER_C.md).

### 4.4 `test_alerts.py` — alert history and resolution (25 cases)

The `scanned` fixture runs all three monitoring scans as ADMIN first, producing the full
set of nine alerts (4 CPU_HIGH + 2 ERROR_DETECTED + 3 LONG_STOPPED).

| Case | Pins |
|---|---|
| `alert_history_is_empty_before_the_first_scan` | Alerts are produced by detection, not by the seed |
| `alert_history_returns_every_detection_newest_first` | Nine alerts, ordered by `detectedAt` descending, all unresolved |
| `alert_history_carries_the_detection_message` | The message records the reading that triggered it (`91.5%`, `96.3%`) |
| `alert_history_filters_by_type` | Each type maps to the expected instances |
| `alert_history_filters_by_resolved_state` | `isResolved=true/false` partition the set |
| `alert_history_filters_by_detection_date` | `dateFrom`/`dateTo` are inclusive and cover the whole day |
| `alert_history_validates_query_parameters` | Bad enum, bad date format, bad boolean → `422` |
| `alert_history_is_scoped_to_the_callers_clients` | manager1 `{1,3,4,5,7,9}`, manager2 `{11,13,14}` |
| `resolving_an_alert_stamps_it_once` | Resolving twice is accepted but `resolvedAt` does not move |
| `resolving_removes_the_alert_from_the_report` | The report count drops from 9 to 8 |
| `resolving_another_managers_alert_is_forbidden` | `403`, and the alert stays unresolved |
| `a_manager_with_no_clients_resolves_nothing` | The same `403` for a caller with an empty scope — the alert guard reaches its client through the instance, so it is the two-hop version of the case above |
| `resolving_an_unknown_alert_is_404` | Body is `{"detail": ...}` with **no** `error` key — the documented shape inconsistency |
| `alert_history_is_paginated` | `size=4` over nine alerts: `4 / 4 / 1`, and `total` stays 9 on every page |
| `alert_pages_partition_the_history_without_gaps_or_repeats` | Every alert of a scan carries the same `detectedAt`, so this passes only because `id` breaks the tie |
| `alert_history_page_past_the_end_is_empty_not_404` | `page=99` is a `200` with empty `items` |
| `alert_history_rejects_out_of_range_paging` | `page=0`, `size=0`, `size=101` → `422` |
| `alert_pagination_applies_after_filtering_and_scoping` | `total` is the scoped, filtered count — 2 for manager1's CPU alerts, not 4 |
| `deleting_an_instance_removes_its_alerts_from_the_history` | No alert outlives its instance. The listing joins `instances` only to scope a `CLIENT_MANAGER`, so an orphaned alert would be hidden from one role and listed to the other ([../performance/PERFORMANCE_BUGS.md § PERF-09](../performance/PERFORMANCE_BUGS.md#perf-09)); the cascade is what stops one existing |

Rules: [../business-rules/ALERTING.md](../business-rules/ALERTING.md),
[../api/ERRORS.md](../api/ERRORS.md) §2.

### 4.5 `test_clients.py` — clients, cost and SLA (27 cases)

| Case | Pins |
|---|---|
| `admin_registers_a_client` | `201`, and the new client immediately appears in its manager's scope |
| `client_registration_is_admin_only` | `403 ADMIN role required`, nothing written |
| `client_registration_rejects_a_manager_id_that_is_not_a_manager` | `400 ValidationError` |
| `client_registration_rejects_an_unknown_manager_id` | `404 NotFound` |
| `client_registration_validates_the_body` | Unknown plan, empty name, non-numeric id → `422` |
| `client_list_is_scoped_by_role` | ADMIN 10, manager1 `1–5`, manager2 `6–10` |
| `a_manager_with_no_clients_sees_nothing` | An empty scope matches nothing, not everything: every scoped list and the report come back empty for a manager with no clients assigned |
| `client_instances_are_listed_for_the_owning_manager` | `[1, 2, 3]` for VinaSoft |
| `client_list_is_paginated` | `size=4` over ten clients: `[1–4]` then `[9, 10]`, `totalPages` 3 |
| `client_list_pagination_counts_only_the_callers_clients` | manager1's `total` is 5, not 10 — the envelope never leaks the table size |
| `client_instances_are_paginated` | `[1, 2]` then `[3]` for VinaSoft |
| `cost_and_sla_still_cover_every_instance_not_a_page` | `costByInstance` and `instanceDetails` stay at 3 rows — the page bound must not leak into the arithmetic |
| `client_sub_resources_enforce_scope_and_existence` | All four sub-resources: `403` across scope, `404` unknown client |
| `current_cost_sums_every_instance_regardless_of_status` | `$620` including the STOPPED instance — stopped instances are still billed |
| `current_cost_follows_a_newly_registered_instance` | Registering a SMALL adds exactly `$50` |
| `forecast_counts_only_running_instances` | `$500`, breakdown by type, STOPPED excluded |
| `forecast_reacts_to_a_status_change` | Starting the STOPPED instance moves the forecast to `$620` |
| `forecast_of_a_client_without_running_instances_is_zero` | `0.0` with an empty breakdown |
| `forecast_groups_all_three_types_of_one_client` | All three types at once with counts that differ, and another client's LARGE instances left out of the LARGE count. The grouping happens in SQL ([../performance/PERFORMANCE_BUGS.md § PERF-12](../performance/PERFORMANCE_BUGS.md#perf-12)), so both the grouping key and the client filter live in the same statement |
| `sla_reports_full_uptime_when_every_instance_is_running` | `100.0%`, `isViolation: false`, threshold `99.0` for STANDARD |
| `sla_flags_a_violation_for_a_long_stopped_instance` | Threshold `95.0` for BASIC, violation flagged, per-instance detail consistent |
| `sla_of_a_client_without_instances_is_not_a_violation` | Empty client is `100.0%`, not `0%` |

Rules: [../business-rules/COST.md](../business-rules/COST.md),
[../business-rules/SLA.md](../business-rules/SLA.md),
[../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md).

### 4.6 `test_diagnosis.py` — the LLM endpoint (7 cases)

| Case | Pins |
|---|---|
| `diagnosis_falls_back_to_a_rule_based_answer` | `source: "rule-based"` with the same three sections the prompt asks the model for |
| `diagnosis_uses_the_model_answer_when_one_is_available` | `source: "llm"` and the model's text returned verbatim |
| `diagnosis_is_given_the_instance_and_its_recent_alerts` | The controller feeds the instance and *its* alerts into the diagnosis |
| `diagnosis_survives_a_provider_failure` | A raising SDK yields `200` + rule-based, never a `5xx` |
| `diagnosis_returns_the_text_the_provider_produced` | Real provider path against a stubbed SDK: prompt carries the instance, thinking blocks are dropped, text blocks are returned |
| `diagnosis_works_for_a_healthy_instance_too` | The endpoint is not restricted to ERROR instances |
| `diagnosis_enforces_scope_and_existence` | `403` / `404` |

Rules: [../design/LLM_FEATURE.md](../design/LLM_FEATURE.md).

---

## 5. Endpoint coverage

Every endpoint in [../api/ENDPOINTS.md](../api/ENDPOINTS.md) is exercised.

| Endpoint | Covered by |
|---|---|
| `GET /` | `test_auth` |
| `POST /api/auth/login` | `test_auth` |
| `POST /api/instances` | `test_instances`, `test_clients` |
| `GET /api/instances` | `test_instances` |
| `GET /api/instances/{id}` | `test_instances` |
| `PATCH /api/instances/{id}/status` | `test_instances`, `test_member_c`, `test_clients` |
| `DELETE /api/instances/{id}` | `test_instances` |
| `GET /api/instances/{id}/diagnosis` | `test_diagnosis` |
| `GET /api/monitor/warnings` · `/errors` · `/long-stopped` | `test_member_c`, `test_alerts` |
| `GET /api/monitor/report` | `test_member_c`, `test_alerts` |
| `GET /api/alerts` | `test_alerts` |
| `PATCH /api/alerts/{id}/resolve` | `test_alerts`, `test_member_c` |
| `POST /api/clients` | `test_clients` |
| `GET /api/clients` | `test_clients` |
| `GET /api/clients/{id}/instances` · `/cost` · `/cost-forecast` · `/sla` | `test_clients` |

Authorization is not a separate suite: each area asserts its own `403` for a cross-scope
call, because scoping is applied per endpoint and a single generic test would not catch a
missing check on one route.

---

## 6. The only stub: the LLM provider

`test_diagnosis.py` replaces the Anthropic call — and nothing else — for two reasons: a
test suite must not depend on a network service or an API key, and a non-deterministic
answer cannot be asserted on.

The autouse `offline` fixture patches `llm_service._llm_diagnosis` to return `None`,
which is exactly the state of a machine with no credentials. Two cases restore the real
function and stub `anthropic.Anthropic` instead, so the provider path — prompt assembly,
response parsing, failure handling — is executed for real against a fake SDK.

No other test touches the network, so the whole suite runs offline.

---

## 7. What is deliberately not covered

Stating these keeps a reader from assuming the gaps are oversights.

| Gap | Why |
|---|---|
| Exact SLA percentages for partially-stopped instances | They depend on the wall clock and the day of the month. The tests assert the *decision* (`isViolation`) and the invariants instead — see [../business-rules/SLA.md](../business-rules/SLA.md) §3 |
| Concurrency and race conditions | Single-process SQLite; the alert dedup check is read-then-write and is not tested under parallel calls |
| Performance and load | Out of scope for the assignment |
| The real Anthropic API | Requires credentials and returns non-deterministic text — [section 6](#6-the-only-stub-the-llm-provider) |
| `cost_snapshots` | Seeded but never read by any endpoint, so there is nothing to assert — noted in [../design/ERD.md](../design/ERD.md) |
| Token expiry over real elapsed time | Simulated by signing a token with a past `exp` rather than waiting two hours |

---

## 8. Adding a test

1. Put it in the suite for its area — a new endpoint gets a section in the file for its
   router, or a new file plus a row in [section 4](#4-the-suites) and
   [section 5](#5-endpoint-coverage).
2. Go through HTTP. Reach for `db` only to assert a side effect the API does not return.
3. Assert exact values. `assert body["totalMonthlyCost"] == 620.0` catches a regression
   that `assert body["totalMonthlyCost"] > 0` does not.
4. Cover the failure paths too — the status code *and* the body shape, since the API has
   two of them ([../api/ERRORS.md](../api/ERRORS.md) §2).
5. Name the test after the behaviour it protects, not the function it calls.
6. Update this document in the same commit, and use the `test:` commit prefix when only
   test code changes — [../contributing/COMMITS.md](../contributing/COMMITS.md).

---

## 9. Related

| Document | Why |
|---|---|
| [RUNNING_TESTS.md](RUNNING_TESTS.md) | How to install and run the suite |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | The contract these tests assert |
| [../api/ERRORS.md](../api/ERRORS.md) | The failure bodies asserted on |
| [../business-rules/](../business-rules/README.md) | The rules each case pins down |
| [../demo/SEED_DATA.md](../demo/SEED_DATA.md) | The fixed data the expectations are built from |
| [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md) | Which document to update alongside a change |
