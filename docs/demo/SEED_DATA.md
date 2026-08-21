# Seed Data

What [app/seed.py](../../app/seed.py) creates on first startup: 3 members, 10 clients,
15 instances, and 10 previous-month cost snapshots.

The seed is **idempotent** — it returns immediately if any member already exists, so
restarting the server never duplicates rows. For a clean database, stop the server,
delete `monitoring.db`, and restart.

No alerts are seeded. Every alert in the system is created by a monitoring scan; see
[../business-rules/ALERTING.md](../business-rules/ALERTING.md).

---

## 1. Members

| id | Email | Role | Name |
|---|---|---|---|
| 1 | `admin@techvalley.vn` | ADMIN | TechValley Admin |
| 2 | `lam@techvalley.vn` | CLIENT_MANAGER | Thai Van Lam |
| 3 | `minh@techvalley.vn` | CLIENT_MANAGER | Nguyen Minh |

Passwords and login instructions: [ACCOUNTS.md](ACCOUNTS.md).

---

## 2. Clients

| id | Client | Plan | Manager | Instances | Monthly cost |
|---|---|---|---|---|---|
| 1 | VinaSoft | PREMIUM | lam | 3 | $620 |
| 2 | Hanoi Logistics | STANDARD | lam | 2 | $170 |
| 3 | Saigon Retail | BASIC | lam | 2 | $100 |
| 4 | Mekong Foods | STANDARD | lam | 1 | $120 |
| 5 | DaNang Media | BASIC | lam | 1 | $250 |
| 6 | VN FinTech | PREMIUM | minh | 2 | $500 |
| 7 | EduViet | STANDARD | minh | 1 | $120 |
| 8 | GreenEnergy VN | BASIC | minh | 1 | $50 |
| 9 | HealthPlus | PREMIUM | minh | 1 | $120 |
| 10 | TravelGo | STANDARD | minh | 1 | $50 |

All three contract plans are represented so the SLA thresholds
(99.9 / 99 / 95) can each be exercised — see
[../business-rules/SLA.md](../business-rules/SLA.md).

---

## 3. Instances

`Launched` and `Stopped/updated` are relative to the moment the seed ran, so the
absolute timestamps differ per machine while the relationships stay fixed.

| id | Name | Region | Type | Status | CPU | Client | Launched | Last update | Triggers |
|---|---|---|---|---|---|---|---|---|---|
| 1 | vinasoft-web-01 | ap-southeast-1 | LARGE | RUNNING | 91.5 | 1 | 90d ago | 1h ago | **CPU_HIGH** |
| 2 | vinasoft-db-01 | ap-southeast-1 | LARGE | RUNNING | 64.0 | 1 | 90d ago | 2h ago | — |
| 3 | vinasoft-batch-01 | ap-northeast-2 | MEDIUM | STOPPED | 0.0 | 1 | 60d ago | 72h ago | **LONG_STOPPED** |
| 4 | hnlog-api-01 | ap-southeast-1 | MEDIUM | RUNNING | 85.2 | 2 | 45d ago | 3h ago | **CPU_HIGH** |
| 5 | hnlog-worker-01 | ap-southeast-1 | SMALL | ERROR | 0.0 | 2 | 45d ago | 6h ago | **ERROR_DETECTED** |
| 6 | sgretail-pos-01 | ap-southeast-1 | SMALL | RUNNING | 42.7 | 3 | 30d ago | 1h ago | — |
| 7 | sgretail-report-01 | ap-southeast-1 | SMALL | STOPPED | 0.0 | 3 | 30d ago | 120h ago | **LONG_STOPPED** |
| 8 | mekong-erp-01 | ap-southeast-1 | MEDIUM | RUNNING | 55.1 | 4 | 20d ago | 2h ago | — |
| 9 | dnmedia-stream-01 | ap-northeast-2 | LARGE | ERROR | 0.0 | 5 | 15d ago | 12h ago | **ERROR_DETECTED** |
| 10 | fintech-core-01 | ap-southeast-1 | LARGE | RUNNING | 78.9 | 6 | 120d ago | 1h ago | — (just under 80) |
| 11 | fintech-core-02 | ap-southeast-1 | LARGE | RUNNING | 88.4 | 6 | 120d ago | 1h ago | **CPU_HIGH** |
| 12 | eduviet-lms-01 | ap-southeast-1 | MEDIUM | RUNNING | 33.0 | 7 | 25d ago | 4h ago | — |
| 13 | green-iot-01 | ap-northeast-2 | SMALL | STOPPED | 0.0 | 8 | 50d ago | 96h ago | **LONG_STOPPED** |
| 14 | health-api-01 | ap-southeast-1 | MEDIUM | RUNNING | 96.3 | 9 | 70d ago | 1h ago | **CPU_HIGH** |
| 15 | travelgo-web-01 | ap-southeast-1 | SMALL | RUNNING | 12.5 | 10 | 10d ago | 1h ago | — |

Instance 10 at **78.9%** is deliberate: it sits just below the 80% threshold, so a demo
can show that the warning scan discriminates rather than returning everything busy.

Two regions (`ap-southeast-1`, `ap-northeast-2`) exist so the `region` filter returns a
meaningful subset.

---

## 4. Totals

| Metric | All (ADMIN) | lam (clients 1–5) | minh (clients 6–10) |
|---|---|---|---|
| Instances | 15 | 9 | 6 |
| RUNNING | 10 | 5 | 5 |
| STOPPED | 3 | 2 | 1 |
| ERROR | 2 | 2 | 0 |
| CPU ≥ 80% warnings | 4 | 2 | 2 |
| Long-stopped (≥ 48h) | 3 | 2 | 1 |
| Total monthly cost | $2,100 | $1,260 | $840 |

Cost by type: 5 × LARGE ($250) + 5 × MEDIUM ($120) + 5 × SMALL ($50) = **$2,100**.

These are the numbers `GET /api/monitor/report` returns on a freshly seeded database
before any status change. They are also the fastest way to verify role scoping — the two
manager columns must sum to the ADMIN column.

---

## 5. Cost snapshots

One `cost_snapshots` row per client for the **previous** calendar month, holding
`totalCost` and `instanceCount` as of seeding.

No endpoint reads these — the table demonstrates the historical-tracking design in the
ERD but month-over-month reporting is not implemented. See
[../business-rules/COST.md](../business-rules/COST.md) and
[../design/ERD.md](../design/ERD.md).

---

## 6. Related

| Document | Why |
|---|---|
| [ACCOUNTS.md](ACCOUNTS.md) | Credentials for reaching this data |
| [WALKTHROUGH.md](WALKTHROUGH.md) | A demo script built around these numbers |
| [../business-rules/](../business-rules/README.md) | The rules these figures exercise |
| [../design/ERD.md](../design/ERD.md) | Table definitions |
