# Authorization Rules

Who can see and do what, once authenticated. The mechanics of obtaining a token are in
[../api/AUTHENTICATION.md](../api/AUTHENTICATION.md); this document covers the rules
applied after the token is validated.

Implementation: [app/core/deps.py](../../app/core/deps.py).

---

## 1. Roles

| Role | Sees | Extra privilege |
|---|---|---|
| `ADMIN` | Every client and every instance | The only role allowed to call `POST /api/clients` |
| `CLIENT_MANAGER` | Only clients where `clients.managerId == member.id`, and those clients' instances and alerts | — |

There is no per-endpoint permission matrix beyond this. Both roles may register
instances, update status, delete, resolve alerts, and run monitoring — a
`CLIENT_MANAGER` is simply restricted to their own clients while doing so.

---

## 2. Two enforcement paths

Scoping is applied differently for list endpoints and single-resource endpoints, and the
distinction matters when reasoning about what a manager can observe.

### 2.1 List endpoints — filter at the query

`accessible_client_ids(member)` returns:

- `None` for `ADMIN` — meaning *no filter*, and the caller sees every row;
- for `CLIENT_MANAGER`, a `SELECT` of their client ids, pushed into a SQL
  `WHERE ... IN (...)` as a subquery.

The scope is a query rather than a list of ids, so it is resolved inside the statement it
filters instead of being fetched first — the request that used to cost the caller an extra
round trip now costs none (docs/performance/PERFORMANCE_BUGS.md § PERF-10). What it
*means* is unchanged: `None` still lets everything through, and a manager still sees only
their own clients' rows.

A manager with **zero** clients yields a subquery that selects no rows, and `IN` over no
rows matches nothing. The result is an empty response, never an unfiltered one — the empty
case is safe rather than accidentally permissive, and
`test_a_manager_with_no_clients_sees_nothing` in
[../../tests/test_clients.py](../../tests/test_clients.py) is what keeps it that way.

Endpoints on this path: `GET /api/instances`, `GET /api/clients`, `GET /api/alerts`, and
all four `GET /api/monitor/*`.

### 2.2 Single-resource endpoints — check after load

`assert_client_access(member, client)` runs once the row has been fetched. It returns
immediately for `ADMIN`, and raises `403` when `client.managerId != member.id`.

Endpoints on this path: every `/api/instances/{id}*`, `/api/clients/{id}/*`, and
`PATCH /api/alerts/{id}/resolve` (which walks `alert.instance.client` to find the owner).

`POST /api/instances` also uses it — the target client is loaded and checked *before*
the instance is created, so a manager cannot plant an instance under someone else's
client.

---

## 3. `403` rather than `404`

When a `CLIENT_MANAGER` requests a resource belonging to another manager's client, the
API answers `403`, confirming the resource exists.

This is a deliberate trade-off. Returning `404` would hide existence, but this is an
internal tool for a single company where instance ids are sequential and not secret, and
a truthful `403` makes misconfigured client assignments obvious during operations
instead of looking like missing data. If the API were ever exposed to the client
companies themselves, this decision should be revisited.

---

## 4. Filters cannot widen visibility

`GET /api/instances?clientId=…` is applied **in addition to** the role scope, not
instead of it. A manager passing another manager's `clientId` gets an empty list —
the two conditions are `AND`-ed. There is no query parameter anywhere in the API that
can broaden what a caller sees.

---

## 5. ADMIN-only client registration

`POST /api/clients` depends on `require_admin`, which raises
`403 {"detail": "ADMIN role required"}` for any other role.

The endpoint also enforces a business constraint on its payload: `managerId` must
reference an existing member **whose role is `CLIENT_MANAGER`**. Pointing a client at an
ADMIN raises `ValidationException` → `400`, because the whole scoping model assumes
every client has exactly one CLIENT_MANAGER owner. See
[../api/ERRORS.md](../api/ERRORS.md).

---

## 6. Stateless tokens, live membership

The JWT carries `role`, but the member row is re-loaded from the database on every
request. A member deleted after their token was issued gets `401 Member no longer
exists` rather than continuing to work until expiry.

A **role change**, however, only takes effect for authorization checks that read
`member.role` from the freshly loaded row — which is all of them. The `role` claim
inside the token is informational for clients and is not trusted for access decisions.

---

## 7. Verification

The role-scoping tests live in [tests/test_member_c.py](../../tests/test_member_c.py):
a manager sees only their own clients' monitoring results, and updating another
manager's instance returns `403`.

---

## 8. Related

| Document | Why |
|---|---|
| [../api/AUTHENTICATION.md](../api/AUTHENTICATION.md) | Getting and sending a token |
| [../api/ERRORS.md](../api/ERRORS.md) | Exact `401` / `403` bodies |
| [../demo/ACCOUNTS.md](../demo/ACCOUNTS.md) | Which demo account manages which clients |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | Steps that demonstrate the `403` path |
