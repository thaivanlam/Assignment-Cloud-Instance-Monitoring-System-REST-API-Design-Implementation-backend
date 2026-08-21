# Business Rules

The domain logic behind the API — thresholds, derived values, and the decisions that
explain *why* an endpoint answers the way it does. Everything here lives in
[app/services/](../../app/services/) and [app/config.py](../../app/config.py), never in
controllers.

| Document | Covers |
|---|---|
| [AUTHORIZATION.md](AUTHORIZATION.md) | Roles, client scoping, ADMIN-only operations, `403` vs `404` |
| [INSTANCE_LIFECYCLE.md](INSTANCE_LIFECYCLE.md) | Registration, status transitions, CPU reset, idempotent updates, the RUNNING delete block |
| [ALERTING.md](ALERTING.md) | Detection thresholds, auto-recording, duplicate prevention, resolution |
| [COST.md](COST.md) | Unit pricing, current-month cost, next-month forecast |
| [SLA.md](SLA.md) | Plan thresholds, uptime approximation, violation flag |

## Configurable values

Every threshold below is a `Settings` field in [app/config.py](../../app/config.py) and
can be overridden through `.env` without touching code.

| Setting | Default | Rule |
|---|---|---|
| `CPU_WARNING_THRESHOLD` | `80.0` | High-CPU warning cut-off — [ALERTING.md](ALERTING.md) |
| `LONG_STOPPED_HOURS` | `48` | Long-stopped cut-off — [ALERTING.md](ALERTING.md) |
| `PRICE_SMALL` / `PRICE_MEDIUM` / `PRICE_LARGE` | `50` / `120` / `250` | Monthly USD unit price — [COST.md](COST.md) |
| `SLA_PREMIUM` / `SLA_STANDARD` / `SLA_BASIC` | `99.9` / `99.0` / `95.0` | Uptime threshold % — [SLA.md](SLA.md) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `120` | JWT lifetime — [../api/AUTHENTICATION.md](../api/AUTHENTICATION.md) |

## Related

| Document | Why |
|---|---|
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | The endpoints these rules govern |
| [../api/ERRORS.md](../api/ERRORS.md) | How a violated rule surfaces to the caller |
| [../design/ERD.md](../design/ERD.md) | Columns the rules read and write |
| [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) | Which test case pins each rule down |
| [../team/MEMBER_C.md](../team/MEMBER_C.md) | Status and monitoring scope in assignment terms |
