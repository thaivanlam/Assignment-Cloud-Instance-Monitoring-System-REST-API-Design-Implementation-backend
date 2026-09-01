# Step 1 — ERD Design

Data model for the TechValley Cloud Instance Monitoring System: five tables implemented
as SQLAlchemy 2.0 ORM entities in [app/models/models.py](../../app/models/models.py).

## Entity Relationship Diagram

```mermaid
erDiagram
    members ||--o{ clients : "manages (managerId)"
    clients ||--o{ instances : "owns (clientId)"
    clients ||--o{ cost_snapshots : "has (clientId)"
    instances ||--o{ alerts : "raises (instanceId)"

    members {
        int id PK
        string email UK "unique, login id"
        string password "PBKDF2 hash"
        string name
        enum role "ADMIN | CLIENT_MANAGER"
        datetime createdAt
    }

    clients {
        int id PK
        string clientName
        enum contractPlan "BASIC | STANDARD | PREMIUM"
        int managerId FK "-> members.id"
        datetime createdAt
    }

    instances {
        int id PK
        string instanceName
        string region
        enum instanceType "SMALL | MEDIUM | LARGE"
        enum status "RUNNING | STOPPED | ERROR"
        float cpuUsage "0-100 (%)"
        float monthlyCost "USD, derived from instanceType"
        int clientId FK "-> clients.id"
        datetime launchedAt
        datetime updatedAt "touched on every status change"
    }

    alerts {
        int id PK
        int instanceId FK "-> instances.id"
        enum alertType "CPU_HIGH | ERROR_DETECTED | LONG_STOPPED"
        string message
        bool isResolved "default false"
        datetime detectedAt
        datetime resolvedAt "nullable"
    }

    cost_snapshots {
        int id PK
        int clientId FK "-> clients.id"
        string snapshotMonth "YYYY-MM"
        float totalCost
        int instanceCount
        datetime createdAt
    }
```

## Relationships

| Relationship | Cardinality | Notes |
|---|---|---|
| members → clients | 1 : N | A CLIENT_MANAGER is responsible for zero or more clients; every client has exactly one manager. |
| clients → instances | 1 : N | Each cloud instance belongs to exactly one client company. |
| instances → alerts | 1 : N | Monitoring endpoints auto-record alerts against instances. |
| clients → cost_snapshots | 1 : N | One snapshot per client per month for historical cost tracking. |

## Indexes

Beyond the primary keys and the unique `members.email`, the columns the API filters and
sorts on are indexed. SQLite creates no index for a foreign key on its own, so without
these every list endpoint was a full table scan —
[../performance/PERFORMANCE_BUGS.md § PERF-04](../performance/PERFORMANCE_BUGS.md#perf-04)
has the measured plans.

| Table | Index | Serves |
|---|---|---|
| `clients` | `managerId` | The accessible-client lookup every `CLIENT_MANAGER` request makes |
| `instances` | `(clientId, status)` | The scope filter on every list and monitoring query, and `?status=` beside it; leading on `clientId` means it serves the scope filter on its own too |
| `instances` | `region` | `GET /api/instances?region=` |
| `instances` | `updatedAt` | `?sort=-updatedAt`, and the 48-hour long-stopped bound |
| `alerts` | `(instanceId, alertType, isResolved)` | The dedup probe each monitoring scan runs once per instance |
| `alerts` | `detectedAt` | `ORDER BY detectedAt DESC`, the sort on every alert listing |

Two omissions are deliberate. **`alerts.isResolved`** is not indexed: nearly every row is
`false`, so SQLite takes the index, matches almost the whole table and then still has to
sort — measurably worse than the ordered `detectedAt` scan it uses instead.
**`cost_snapshots.clientId`** is not indexed because no endpoint reads the table (see
[Known Gaps](#known-gaps)).

Indexes are created at startup by `lifespan` in [app/main.py](../../app/main.py), one
`CREATE INDEX` per index with `checkfirst=True`. `create_all` on its own is not enough:
it skips a table that already exists, its indexes included, so an index declared after a
database file was created would never appear in that file.

## Design Notes

- **Column names use camelCase** to mirror the assignment specification exactly (`createdAt`, `managerId`, `cpuUsage`, ...).
- **`monthlyCost` is derived** from `instanceType` at registration time using the unit pricing table (SMALL $50 / MEDIUM $120 / LARGE $250) but stored for reporting speed and historical accuracy if pricing changes.
- **`updatedAt`** is refreshed on every status change; it drives both the *long-stopped (48h+)* detection and the SLA uptime approximation (the schema has no status-history table, so the last transition time is the best available signal).
- **`alerts.isResolved` + `resolvedAt`** support the dedup rule: monitoring calls skip alert creation when an unresolved alert of the same type already exists for the instance.
- **`cost_snapshots.snapshotMonth`** is stored as a `YYYY-MM` string for simple grouping and uniqueness per client-month.

## Known Gaps

- **No status-history table.** Only `updatedAt` records that a status changed, not the sequence of changes. This is the source of the SLA uptime approximation and its limits — see [../business-rules/SLA.md](../business-rules/SLA.md). Adding `instance_status_history(instanceId, fromStatus, toStatus, changedAt)` would make uptime exact.
- **`cost_snapshots` is written but never read.** The seed creates one previous-month row per client; no endpoint consumes them, so month-over-month cost reporting is designed for but not implemented — see [../business-rules/COST.md](../business-rules/COST.md).
- **No migrations.** Tables are created from the ORM metadata at startup, so a schema change means deleting `monitoring.db` rather than migrating it — see [ARCHITECTURE.md](ARCHITECTURE.md). Indexes are the one exception: startup creates each missing one against the existing file, so adding an index needs no rebuild.
- **Alerts cascade with their instance.** Deleting an instance removes its alert history, so incident records do not outlive the resource they describe.

## Related

| Document | Why |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the models fit the MVC layering |
| [../business-rules/](../business-rules/README.md) | Rules that read and write these columns |
| [../api/OVERVIEW.md](../api/OVERVIEW.md) | Enum values as they appear over HTTP |
| [../demo/SEED_DATA.md](../demo/SEED_DATA.md) | Rows the seed creates in these tables |
