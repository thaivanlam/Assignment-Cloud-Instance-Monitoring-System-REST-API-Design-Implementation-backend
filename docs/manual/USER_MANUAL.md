# User Manual

| | |
|---|---|
| System | TechValley Cloud Instance Monitoring System |
| Audience | Administrators, client managers and on-call engineers using the system |
| Version | API `1.0.0` |
| Last reviewed | 2026-09-01 |

How to operate the system: signing in, finding and updating instances, running the
monitoring checks, working the alert queue, and producing cost and SLA figures for a
client. Written for the person doing the work — no knowledge of the code is assumed.

**Contents**

1. [What this system does](#1-what-this-system-does)
2. [Before you start](#2-before-you-start)
3. [Signing in](#3-signing-in)
4. [Finding your way around a response](#4-finding-your-way-around-a-response)
5. [Working with instances](#5-working-with-instances)
6. [Checking for trouble](#6-checking-for-trouble)
7. [Working the alert queue](#7-working-the-alert-queue)
8. [Cost and forecasting](#8-cost-and-forecasting)
9. [SLA reporting](#9-sla-reporting)
10. [Getting a diagnosis](#10-getting-a-diagnosis)
11. [Managing client companies](#11-managing-client-companies)
12. [When something goes wrong](#12-when-something-goes-wrong)
13. [Frequently asked questions](#13-frequently-asked-questions)
14. [Glossary](#14-glossary)

---

## 1. What this system does

It is the register of every cloud instance TechValley operates for its client companies,
and the tool that watches them. With it you can:

- **record** an instance against a client, and keep its status current;
- **find** instances by status, client, region, type or CPU load;
- **detect** instances that are overloaded, failed, or stopped and forgotten — and keep a
  record of each detection until somebody deals with it;
- **report** what a client costs this month, what next month looks like, and whether its
  contracted uptime is being met;
- **ask for a written diagnosis** of an unhealthy instance.

**What it does not do.** It is a record, not a control panel. Marking an instance
`STOPPED` here records that it is stopped — it does not stop a machine at your cloud
provider. It sends no email or chat notifications; alerts are things you come and read. And
it runs no checks on its own schedule: a check happens when someone (or a dashboard) asks
for it — see [§ 6](#6-checking-for-trouble).

---

## 2. Before you start

### 2.1 Starting the system

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows;  Linux/macOS:  source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The database is created and filled with demo data the first time it starts. Confirm it is
alive by opening <http://127.0.0.1:8000/> — you should see
`{"status":"ok", …}`.

Deploying it somewhere other than your own machine:
[../operations/DEPLOYMENT.md](../operations/DEPLOYMENT.md).

### 2.2 The two ways to use it

| Way | Best for |
|---|---|
| **Swagger UI** — <http://127.0.0.1:8000/docs> | Everyday use. Every operation is a form in the browser; you never type a URL |
| **`curl` or any HTTP client** | Scripting, or pasting a reproducible command into a ticket |

This manual shows both: the Swagger steps first, then the equivalent command.

### 2.3 Accounts and what each one sees

| Role | Sees | Can also |
|---|---|---|
| **Administrator** (`ADMIN`) | Every client and every instance | Register new client companies |
| **Client manager** (`CLIENT_MANAGER`) | Only the clients assigned to them, and those clients' instances and alerts | — |

Both roles can register instances, change status, delete, run the monitoring checks and
resolve alerts. A manager is simply confined to their own clients while doing so.

The demo accounts, and which clients each manages, are in
[../demo/ACCOUNTS.md](../demo/ACCOUNTS.md).

---

## 3. Signing in

Nothing except the health check works until you have a token.

**In Swagger UI**

1. Open <http://127.0.0.1:8000/docs>.
2. Find `POST /api/auth/login`, click **Try it out**.
3. Replace the example body with your email and password, and click **Execute**.
4. Copy the `accessToken` value from the response — the long string in quotes.
5. Click **Authorize** at the top right, paste the token, confirm, and close the dialog.

Every operation you run from now on carries the token automatically.

**With curl**

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"lam@techvalley.vn","password":"manager123!"}'
```

Keep the `accessToken` and send it on every later call:

```bash
curl -H "Authorization: Bearer <accessToken>" http://127.0.0.1:8000/api/monitor/report
```

**Things to know**

- A token lasts **120 minutes**. When it expires you get
  `401 {"detail": "Token has expired"}` — sign in again. There is no "stay signed in".
- There is no sign-out. Closing the browser is enough for practical purposes; the token
  simply expires.
- To switch users, repeat the steps above with the other account's credentials.
- If your email or password is wrong you get the same message either way —
  `Invalid email or password`. That is deliberate, so the login page cannot be used to
  work out who has an account.

---

## 4. Finding your way around a response

### 4.1 Lists come one page at a time

Every list — instances, alerts, clients, monitoring results — arrives in the same wrapper:

```json
{
  "items": [ … ],
  "total": 15,
  "page": 1,
  "size": 10,
  "totalPages": 2
}
```

| Field | Meaning |
|---|---|
| `items` | The rows on this page |
| `total` | How many rows match **in total** — after your filters *and* what you are allowed to see |
| `page`, `size` | What you asked for. `size` may be 1–100; the default is 10 |
| `totalPages` | How many pages there are altogether |

Ask for the next page with `?page=2`, or fewer/more rows at a time with `?size=25`.
Asking for a page beyond the end returns an empty `items` list, not an error — so a loop
that keeps asking for the next page ends cleanly.

If you are a client manager, `total` counts **your** rows only. It never tells you how
much data exists outside your scope.

### 4.2 Values you will see

| Thing | Format | Example |
|---|---|---|
| Dates and times | ISO-8601, **UTC**, no timezone suffix | `2026-08-21T14:07:00` |
| Status, type, plan, alert type | UPPERCASE words | `RUNNING`, `LARGE`, `PREMIUM`, `CPU_HIGH` |
| Money | US dollars per month | `250.0` |
| CPU and uptime | A percentage between 0 and 100 — not a fraction | `91.5` |

Times are UTC. If your working day is UTC+7, an instance stamped `02:00` changed at
09:00 local.

---

## 5. Working with instances

### 5.1 Finding instances

`GET /api/instances` is the main listing. Combine any of these, in Swagger's form fields
or as query parameters:

| To see | Use |
|---|---|
| Only running instances | `status=RUNNING` |
| One client's instances | `clientId=1` |
| One region | `region=ap-southeast-1` (exact spelling, case-sensitive) |
| One size | `instanceType=LARGE` |
| Busiest first | `sort=-cpuUsage` |
| By name, A–Z | `sort=instanceName` |

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/instances?status=RUNNING&sort=-cpuUsage&size=5"
```

Filters combine — `status=RUNNING&region=ap-southeast-1` gives you running instances in
that region only.

**Two behaviours worth knowing.** Filtering by a client you do not manage returns an
*empty list* rather than an error: a filter can only narrow what you see, never widen it.
And if you misspell the `sort` field, the list comes back sorted by `id` instead of
failing — so if an ordering looks wrong, check the spelling first.

To see one instance in full, use `GET /api/instances/{id}`.

### 5.2 Registering an instance

`POST /api/instances`. Send:

| Field | Required | Notes |
|---|:--:|---|
| `instanceName` | ✓ | 1–100 characters |
| `region` | ✓ | e.g. `ap-southeast-1` |
| `instanceType` | ✓ | `SMALL`, `MEDIUM` or `LARGE` |
| `clientId` | ✓ | Must be a client you manage |
| `status` | | Defaults to `RUNNING` |
| `cpuUsage` | | Defaults to `0.0` |

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"instanceName":"vinasoft-cache-01","region":"ap-southeast-1",
       "instanceType":"MEDIUM","clientId":1}' \
  http://127.0.0.1:8000/api/instances
```

**You do not set the price.** The monthly cost comes from the size you chose —
SMALL `$50`, MEDIUM `$120`, LARGE `$250` — and the system fills it in. Anything you send
in a cost field is ignored. This is why the cost report can be trusted: nobody can type a
wrong number into it.

The instance's cost appears in that client's total straight away.

### 5.3 Changing an instance's status

`PATCH /api/instances/{id}/status` with the new `status`, and optionally a `cpuUsage`
reading.

```bash
curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"STOPPED"}' \
  http://127.0.0.1:8000/api/instances/1/status
```

| What you send | What happens |
|---|---|
| `STOPPED` or `ERROR`, no CPU value | CPU is set to `0.0` — a stopped instance is not using any, and a stale reading would keep it in the warning list forever |
| Any status **with** a `cpuUsage` | Your value is used, exactly as given |
| `RUNNING`, no CPU value | The last known reading is left alone |
| A status and CPU **identical to what is already stored** | Nothing changes at all — see the note below |

Any status can follow any other. An instance may go from `ERROR` straight to `RUNNING`
after a restart; you do not have to stop it in between.

> **Why a "no change" update changes nothing.** The system remembers when an instance last
> changed state, and it uses that to work out how long something has been stopped and to
> calculate uptime. If re-sending the same status refreshed that timestamp, an instance
> stopped for a week would look as though it had just stopped, and it would never show up
> as idle. So an update that changes neither the status nor the CPU is accepted and
> ignored. If you expected a timestamp to move and it did not, this is why.

### 5.4 Deleting an instance

`DELETE /api/instances/{id}` — but **a running instance cannot be deleted**:

```json
{
  "error": "ActiveInstanceException",
  "detail": "Instance 1 is RUNNING and cannot be deleted. Stop it first."
}
```

Stop it first, then delete it:

```bash
curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"status":"STOPPED"}' http://127.0.0.1:8000/api/instances/1/status
curl -X DELETE -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/instances/1
```

A successful delete answers with **no content** — that is the normal, successful result,
not an empty response you should worry about.

> **Deleting is permanent, and it takes the alert history with it.** Every alert ever
> raised for that instance is removed too. If you may need the incident record later,
> export it from `GET /api/alerts` before deleting.

---

## 6. Checking for trouble

Three checks find the three things that go wrong. Each returns the instances it found and
**records an alert for each one**, so the problem is on the record even if you get
distracted.

| Check | Finds | Records |
|---|---|---|
| `GET /api/monitor/warnings` | Running instances at **80% CPU or above** | `CPU_HIGH` |
| `GET /api/monitor/errors` | Instances in `ERROR` | `ERROR_DETECTED` (critical) |
| `GET /api/monitor/long-stopped` | Instances stopped for **48 hours or more** | `LONG_STOPPED` |

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/monitor/warnings
```

**Run them as often as you like.** Running a check twice does not create the alert twice:
while an alert of that kind is still open for an instance, the check skips it. You will
see the same instances listed each time — that is the current state, not a new incident.

**Paging does not limit what gets detected.** If 40 instances are overloaded and you ask
for `size=10`, you see ten of them, `total` says 40, and **all 40** alerts are recorded.
You never have to page to the end to make sure everything was caught.

If you are a client manager, each check covers your clients only, and creates alerts only
for your instances.

### The one-call summary

`GET /api/monitor/report` answers "how are things right now?" in a single call:

```json
{
  "generatedAt": "2026-08-21T09:20:00",
  "instanceCountByStatus": { "RUNNING": 10, "STOPPED": 3, "ERROR": 2 },
  "warningCount": 4,
  "totalMonthlyCost": 2100.0,
  "unresolvedAlertCount": 9,
  "unresolvedAlerts": [ … ]
}
```

Two things to read correctly:

- `totalMonthlyCost` covers instances of **every** status, because a stopped instance is
  still costing money this month.
- `unresolvedAlerts` shows only the **20 most recent** open alerts, while
  `unresolvedAlertCount` is the true number. If the count says 60 and you can see 20, the
  other 40 are in `GET /api/alerts`.

The report is read-only: it creates no alerts. Use it freely.

---

## 7. Working the alert queue

### 7.1 Reading the history

`GET /api/alerts`, newest first. Narrow it with:

| To see | Use |
|---|---|
| One kind of problem | `alertType=CPU_HIGH` (or `ERROR_DETECTED`, `LONG_STOPPED`) |
| Only open items | `isResolved=false` |
| Only handled items | `isResolved=true` |
| A date range | `dateFrom=2026-08-01&dateTo=2026-08-21` (both days included) |

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/alerts?isResolved=false&alertType=CPU_HIGH&size=50"
```

Each alert says which instance it belongs to, when it was detected, and — in `message` —
the reading that triggered it, e.g. `CPU usage 91.5% >= 80% on instance 'vinasoft-web-01'
(ap-southeast-1)`. You do not need to look up the instance to know what happened.

### 7.2 Marking one handled

`PATCH /api/alerts/{id}/resolve` once you have dealt with the underlying problem.

```bash
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/alerts/3/resolve
```

The alert is stamped with the time you resolved it and drops out of the report's open
count.

**Three things that surprise people:**

1. **Nothing resolves itself.** An instance that recovers from `ERROR` back to `RUNNING`
   keeps its open alert until you close it. That is on purpose — the record that the
   incident happened should not vanish because the symptom did.
2. **Resolving re-arms the check.** If you resolve a CPU alert and the CPU is still high,
   the next check opens a **new** alert. You are being told again because the problem is
   still there.
3. **Resolving twice is harmless.** The original resolution time is kept; a second click
   cannot overwrite the record of when it was handled.

---

## 8. Cost and forecasting

### 8.1 What a client costs this month

`GET /api/clients/{id}/cost`

```json
{
  "clientId": 1, "clientName": "VinaSoft", "month": "2026-08",
  "instanceCount": 3, "totalMonthlyCost": 620.0,
  "costByInstance": [ { "instanceId": 1, "instanceName": "vinasoft-web-01",
                        "instanceType": "LARGE", "status": "RUNNING",
                        "monthlyCost": 250.0 } ]
}
```

**Stopped and failed instances are included.** A provisioned instance costs money for the
month whether or not it is running. That is why each row shows its `status`: it tells you
what you are still paying for and could decommission.

### 8.2 What next month looks like

`GET /api/clients/{id}/cost-forecast` — the same client, counting only what is **running
right now**, grouped by size:

```json
{
  "clientId": 1, "forecastMonth": "2026-09",
  "runningInstanceCount": 2, "forecastCost": 500.0,
  "breakdown": { "LARGE": { "count": 2, "unitPrice": 250.0, "subtotal": 500.0 } }
}
```

The difference between the two figures is the useful part: this month's cost is what you
are already committed to; the forecast is what next month costs **if the stopped instances
stay stopped**. A large gap between them is a decommissioning opportunity.

A client with nothing running forecasts `0.0` with an empty breakdown — that is a valid
answer, not an error. Sizes with nothing running are left out rather than shown as zero.

---

## 9. SLA reporting

`GET /api/clients/{id}/sla` reports the client's uptime this month against the promise its
contract plan carries:

| Plan | Promised uptime |
|---|---|
| `PREMIUM` | 99.9% |
| `STANDARD` | 99% |
| `BASIC` | 95% |

`isViolation` is `true` when the measured figure falls **below** the threshold. Exactly
meeting it is not a violation.

`instanceDetails` shows the working: for each instance, how many hours were measured
(`measuredHours`), how many counted as up (`runningHours`), and the resulting percentage.
When a client shows a violation, this is where you find out which instance caused it.

> ### Read this before quoting an SLA figure to a client
>
> The number is an **estimate, not a measurement**. The system records only an instance's
> *most recent* status change, so it cannot see a history of outages. In practice:
>
> - an instance that failed and recovered three times this month is currently running, so
>   it is credited with **100% uptime** — real downtime is under-reported;
> - a current outage is assumed to have begun at the last recorded change;
> - every instance counts equally, so a small test box weighs as much as a production
>   database.
>
> Use it to spot a client that is in trouble **now**. Do not put it in a contractual
> report. The full explanation is in
> [../business-rules/SLA.md](../business-rules/SLA.md).

---

## 10. Getting a diagnosis

`GET /api/instances/{id}/diagnosis` produces a written incident note for one instance —
probable causes, recommended actions, and how to prevent a recurrence — based on the
instance's details and its ten most recent alerts.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/instances/5/diagnosis
```

Check the `source` field in the answer:

| `source` | Meaning |
|---|---|
| `"llm"` | Written by the AI model, using this instance's history |
| `"rule-based"` | Written from built-in rules, because the model was not available |

Both are useful; the rule-based answer is shorter and more generic. You get one or the
other **always** — a missing API key, a slow model or a provider outage never leaves you
without an answer, and never produces an error. The call can take up to about a minute in
the worst case before falling back.

It works on healthy instances too, if you want a second opinion before making a change.

---

## 11. Managing client companies

### 11.1 Listing clients

`GET /api/clients` shows the clients you are responsible for — all ten if you are an
administrator, your own if you are a manager. `GET /api/clients/{id}/instances` lists one
client's instances.

### 11.2 Registering a client — administrators only

`POST /api/clients`:

```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"clientName":"NewCo","contractPlan":"STANDARD","managerId":2}' \
  http://127.0.0.1:8000/api/clients
```

| Field | Notes |
|---|---|
| `clientName` | 1–100 characters |
| `contractPlan` | `BASIC`, `STANDARD` or `PREMIUM` — this sets the SLA promise |
| `managerId` | The member id of the **client manager** who will own this account |

The manager you name must be a client manager, not an administrator. Pointing a client at
an administrator is refused with `400`, because every client needs exactly one manager
owner — otherwise nobody would see it in their own list.

If you are a client manager, this operation answers `403 ADMIN role required`. Ask an
administrator.

---

## 12. When something goes wrong

Every failure comes back with a `detail` line in plain words. Read that first.

| You see | It means | Do this |
|---|---|---|
| `401 Not authenticated. Provide a Bearer token.` | You did not send a token | Sign in, and in Swagger click **Authorize** |
| `401 Token has expired` | More than 120 minutes since you signed in | Sign in again |
| `401 Invalid token` | The token is damaged or was issued by a different system | Sign in again; copy the whole token |
| `401 Invalid email or password` | Wrong credentials — it will not say which | Re-type both. Nobody can tell you which half was wrong; that is by design |
| `401 Member no longer exists` | Your account was removed after you signed in | Contact an administrator |
| `403 ADMIN role required` | Only administrators can register clients | Ask an administrator |
| `403 CLIENT_MANAGER can only access clients assigned to them` | The instance, client or alert belongs to another manager | Check the id. If it should be yours, ask an administrator to reassign the client |
| `404 NotFound` / `Alert {id} not found` | No such instance, client or alert | Check the id; it may have been deleted |
| `409 ActiveInstanceException` | You tried to delete a running instance | Stop it, then delete it ([§ 5.4](#54-deleting-an-instance)) |
| `400 ValidationError` | The request was well-formed but breaks a business rule — nearly always a `managerId` that is not a client manager | Use a manager's id |
| `422` with a list of field problems | A value is the wrong type or out of range — `cpuUsage` above 100, `size` above 100, an unknown status, a date that is not `YYYY-MM-DD` | Read `loc` in the response: it names the offending field |
| An empty list where you expected rows | Usually a filter you did not mean, or a client outside your scope | Remove filters one at a time; check `total` |

If the server itself will not start or has stopped answering, that is an operations
problem: [../operations/RUNBOOKS.md](../operations/RUNBOOKS.md).

---

## 13. Frequently asked questions

**Does marking an instance `STOPPED` actually stop it?**
No. This system records state; it does not control infrastructure. Stop the machine at
your cloud provider, then record it here.

**Will it email me when something breaks?**
No. Alerts are recorded for you to read. Check `GET /api/monitor/report` at the start of a
shift, or have a dashboard poll the monitoring endpoints.

**Does it check by itself overnight?**
No. A check runs when someone calls one of the three monitoring endpoints. If nothing polls
them over the weekend, nothing is detected until Monday — though the conditions are all
based on current state, so the Monday check finds everything that is still wrong.

**Why did my instance not appear in the warnings list?**
The warning check only looks at **running** instances at 80% CPU or above. An instance at
78.9% is below the line, and a stopped instance is excluded no matter what CPU figure it
shows.

**I resolved an alert and it came straight back.**
The problem is still there. Resolving tells the system you have handled *this* report;
if the condition still holds at the next check, you are told again.

**Why can I see that an instance exists but not read it?**
Cross-scope requests answer `403`, not `404` — you are told the thing exists and is not
yours. That is deliberate: it makes a wrongly assigned client obvious instead of looking
like missing data.

**Can I have more than 100 rows in one response?**
No; `size` is capped at 100. Ask for the next page instead. Nothing in the API returns an
unbounded list.

**Are the demo passwords a security problem?**
They are demo credentials for a local database and are documented on purpose. Before any
real deployment, read [../operations/CONFIGURATION.md](../operations/CONFIGURATION.md) —
particularly about changing the signing key — and
[../security/SECURITY_BUGS.md](../security/SECURITY_BUGS.md).

---

## 14. Glossary

| Term | Meaning |
|---|---|
| **Instance** | One cloud machine recorded in the system, belonging to one client |
| **Client** | A company you operate instances for. Clients do not sign in |
| **Member** | A TechValley staff account — an administrator or a client manager |
| **Contract plan** | `BASIC`, `STANDARD` or `PREMIUM`; sets the client's uptime promise |
| **Alert** | A recorded detection, open until someone resolves it |
| **Check / scan** | One call to a monitoring endpoint: it lists what it found and records alerts |
| **Warning** | A running instance at 80% CPU or above |
| **Long-stopped** | Stopped for 48 hours or more |
| **Resolve** | Mark an alert as handled |
| **Forecast** | Next month's cost, counting only what is running now |
| **Violation** | Uptime below the client's plan threshold |
| **Token** | The string you get from signing in and send on every request |

---

## 15. Related

| Document | Why |
|---|---|
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | A 29-step guided tour with the exact numbers to expect |
| [../demo/ACCOUNTS.md](../demo/ACCOUNTS.md) | Demo credentials and who manages which clients |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | Every field of every request and response |
| [../api/ERRORS.md](../api/ERRORS.md) | The complete error reference behind [§ 12](#12-when-something-goes-wrong) |
| [../business-rules/](../business-rules/README.md) | Why the rules in this manual are what they are |
| [../operations/RUNBOOKS.md](../operations/RUNBOOKS.md) | When the server, not your request, is the problem |
| [../screenshots/README.md](../screenshots/README.md) | What each screen looks like in Swagger UI |
