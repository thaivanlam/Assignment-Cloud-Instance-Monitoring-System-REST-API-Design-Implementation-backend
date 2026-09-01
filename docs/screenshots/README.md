# Screenshots

Swagger UI responses captured against a freshly seeded database by
[scripts/capture_swagger_ui.py](../../scripts/capture_swagger_ui.py). They follow the
order of [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md).

Numbers in these captures reflect the seed state at capture time — see
[../demo/SEED_DATA.md](../demo/SEED_DATA.md).

## Keeping them current

A capture is documentation: when a change alters a route, a field, a status code, an
error body or the seed numbers, the affected PNG is re-captured in the same commit —
rule 6 of
[../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md#6-screenshots-follow-the-api).

```bash
uvicorn app.main:app --reload                                  # terminal 1
python scripts/capture_swagger_ui.py --only instance_create    # terminal 2
```

`--only` is a substring filter on the scenario name — the part of the filename after the
number. Omit it to rebuild all 29, after deleting `monitoring.db` so the run starts from
a clean seed. Adding or removing a scenario also means adding or removing its row below.

## Auth

| Screenshot | Shows |
|---|---|
| [01_health.png](01_health.png) | `GET /` health check |
| [02_login_admin.png](02_login_admin.png) | `POST /api/auth/login` as ADMIN → `accessToken` |
| [03_login_wrong_password.png](03_login_wrong_password.png) | `401` on bad credentials |
| [28_instances_unauthorized_401.png](28_instances_unauthorized_401.png) | `401` with no Bearer token |

## Clients

| Screenshot | Shows |
|---|---|
| [04_clients_list_admin.png](04_clients_list_admin.png) | All 10 clients as ADMIN |
| [05_client_create.png](05_client_create.png) | `POST /api/clients` → `201` |
| [19_client_instances.png](19_client_instances.png) | `GET /api/clients/{id}/instances` |
| [20_client_cost.png](20_client_cost.png) | Current-month cost total |
| [21_client_cost_forecast.png](21_client_cost_forecast.png) | Next-month forecast, RUNNING only |
| [22_client_sla.png](22_client_sla.png) | SLA uptime with per-instance detail |

## Instances

| Screenshot | Shows |
|---|---|
| [06_instances_list_sorted.png](06_instances_list_sorted.png) | `?sort=-cpuUsage` with pagination envelope |
| [07_instances_list_filtered.png](07_instances_list_filtered.png) | Status and region filters |
| [08_instance_get.png](08_instance_get.png) | Single instance |
| [09_instance_create.png](09_instance_create.png) | `201`, with `monthlyCost` derived from type |
| [10_instance_update_status.png](10_instance_update_status.png) | `PATCH .../status`, CPU reset on STOPPED |
| [11_instance_diagnosis_llm.png](11_instance_diagnosis_llm.png) | LLM diagnosis with `source` |

## Monitoring and alerts

| Screenshot | Shows |
|---|---|
| [12_monitor_warnings.png](12_monitor_warnings.png) | CPU ≥ 80% instances |
| [13_monitor_errors.png](13_monitor_errors.png) | ERROR instances |
| [14_monitor_long_stopped.png](14_monitor_long_stopped.png) | STOPPED ≥ 48h instances |
| [15_monitor_report.png](15_monitor_report.png) | Full aggregate report |
| [16_alerts_list.png](16_alerts_list.png) | Alert history |
| [17_alerts_list_filtered.png](17_alerts_list_filtered.png) | Filtered by type and resolved state |
| [18_alert_resolve.png](18_alert_resolve.png) | `PATCH /api/alerts/{id}/resolve` |

## Error paths and role scoping

| Screenshot | Shows |
|---|---|
| [23_delete_running_409.png](23_delete_running_409.png) | `409 ActiveInstanceException` |
| [24_instance_not_found_404.png](24_instance_not_found_404.png) | `404 NotFound` |
| [29_delete_stopped_204.png](29_delete_stopped_204.png) | `204` deleting a STOPPED instance |
| [25_clients_list_manager.png](25_clients_list_manager.png) | CLIENT_MANAGER sees only their clients |
| [26_client_sla_forbidden_403.png](26_client_sla_forbidden_403.png) | `403` on another manager's client |
| [27_client_create_forbidden_403.png](27_client_create_forbidden_403.png) | `403 ADMIN role required` |

## Related

| Document | Why |
|---|---|
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | The steps these images capture |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | Reference for each endpoint shown |
| [../api/ERRORS.md](../api/ERRORS.md) | The error bodies in the last section |
