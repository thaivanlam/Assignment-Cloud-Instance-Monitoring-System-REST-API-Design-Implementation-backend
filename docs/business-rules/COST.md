# Cost Rules

Unit pricing, current-month cost, and next-month forecast.
Implementation: [app/services/client_service.py](../../app/services/client_service.py)
and [app/config.py](../../app/config.py).

---

## 1. Unit pricing

| `instanceType` | Monthly price (USD) | Setting |
|---|---|---|
| `SMALL` | `$50` | `PRICE_SMALL` |
| `MEDIUM` | `$120` | `PRICE_MEDIUM` |
| `LARGE` | `$250` | `PRICE_LARGE` |

Prices are flat monthly figures, not hourly rates — this system tracks committed
contract cost, not metered usage. All three are `Settings` fields and can be overridden
via `.env`.

---

## 2. `monthlyCost` is derived but stored

At registration, `monthlyCost` is looked up from `instanceType` and written to the
`instances` row. It is never accepted from the request body.

Storing a derived value is a deliberate denormalisation, for two reasons:

- **Reporting speed** — `GET /api/monitor/report` sums the column directly in SQL rather
  than joining and mapping every row through a price table in Python.
- **Historical accuracy** — if pricing changes, existing instances keep the price they
  were registered at. Recomputing on read would silently rewrite the past.

The trade-off is that a price change in `.env` does **not** retroactively update
existing instances. Only newly registered instances pick up the new figure. Repricing
existing rows would require a migration.

---

## 3. Current-month cost — `GET /api/clients/{id}/cost`

Sums `monthlyCost` across **all** of the client's instances, regardless of status, and
reports the current month as `YYYY-MM`.

```json
{
  "clientId": 1,
  "clientName": "VinaSoft",
  "month": "2026-08",
  "instanceCount": 3,
  "totalMonthlyCost": 620.0,
  "costByInstance": [
    { "instanceId": 1, "instanceName": "vinasoft-web-01", "instanceType": "LARGE",
      "status": "RUNNING", "monthlyCost": 250.0 }
  ]
}
```

Including stopped and failed instances is intentional: a provisioned instance keeps
costing money for the month whether or not it is currently running. `costByInstance`
carries each instance's `status` so a caller can present the breakdown and let the
operator decide what to decommission.

`totalMonthlyCost` is rounded to 2 decimals.

**This endpoint is not paginated**, and `costByInstance` covers every instance of the
client rather than a page of them. `GET /api/clients/{id}/instances` beside it *is*
paginated ([../api/CONVENTIONS.md § 1](../api/CONVENTIONS.md#1-pagination)), and the
difference is deliberate: a total that summed one page would be wrong, so the rows have
to be loaded regardless and there is nothing to save by bounding the array they produce.
Both read the same query, `_client_instances_query` in
[client_service.py](../../app/services/client_service.py); only the listing endpoint
takes a page from it.

---

## 4. Next-month forecast — `GET /api/clients/{id}/cost-forecast`

Counts only instances that are **currently `RUNNING`**, grouped by type:

```
forecastCost = Σ (unit price of type × count of RUNNING instances of that type)
```

```json
{
  "clientId": 1,
  "clientName": "VinaSoft",
  "forecastMonth": "2026-09",
  "runningInstanceCount": 2,
  "forecastCost": 500.0,
  "breakdown": { "LARGE": { "count": 2, "unitPrice": 250.0, "subtotal": 500.0 } }
}
```

The RUNNING-only rule is the difference between this endpoint and the one above.
Current cost is *what is already committed*; the forecast is *what next month looks like
if nothing changes* — and a stopped instance is the operator's signal that it will be
decommissioned.

Details worth knowing:

- `breakdown` contains only types that have at least one RUNNING instance. A client
  with no RUNNING LARGE instances has no `LARGE` key at all, rather than a zero entry.
- `forecastMonth` rolls the year correctly in December (`2026-12` → `2027-01`).
- A client with no RUNNING instances returns `forecastCost: 0.0` and an empty
  `breakdown`, not an error.

The forecast is a straight-line projection. It does not model growth, seasonality, or
planned changes, and it assumes the current mix holds for the whole of next month.

---

## 5. Cost in the monitoring report

`GET /api/monitor/report` reports `totalMonthlyCost` over every instance visible to the
caller — same all-status rule as §3, but scoped to the caller's clients rather than one
client. See [ALERTING.md](ALERTING.md).

---

## 6. `cost_snapshots`

The `cost_snapshots` table stores one `(clientId, snapshotMonth, totalCost,
instanceCount)` row per client per month for historical tracking. The seed writes a
previous-month snapshot for every client
([../demo/SEED_DATA.md](../demo/SEED_DATA.md)).

No endpoint currently reads or writes snapshots — the table exists in the schema and is
populated by the seed, but month-over-month reporting is not implemented. See
[../design/ERD.md](../design/ERD.md).

---

## 7. Related

| Document | Why |
|---|---|
| [INSTANCE_LIFECYCLE.md](INSTANCE_LIFECYCLE.md) | Where `monthlyCost` is set |
| [SLA.md](SLA.md) | The other per-client calculation |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | Response shapes |
| [../design/ERD.md](../design/ERD.md) | `instances.monthlyCost`, `cost_snapshots` |
