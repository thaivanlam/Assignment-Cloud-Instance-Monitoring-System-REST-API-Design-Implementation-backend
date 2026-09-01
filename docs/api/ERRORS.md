# Errors

Status codes and response bodies for every failure path.

---

## 1. Status codes

| Code | When |
|---|---|
| `200` | Successful read or update |
| `201` | `POST /api/instances`, `POST /api/clients` |
| `204` | `DELETE /api/instances/{id}` — no response body |
| `400` | Business-rule validation failure (`ValidationException`) |
| `401` | Missing, expired, or invalid JWT |
| `403` | Role or client-scope violation |
| `404` | Resource does not exist |
| `409` | `ActiveInstanceException` — deleting a RUNNING instance |
| `422` | Request body or query parameter fails schema validation |

There is deliberately **no** `502`/`503` for LLM outages. `GET /api/instances/{id}/diagnosis`
absorbs provider failures and returns `200` with `"source": "rule-based"` — see
[../design/LLM_FEATURE.md](../design/LLM_FEATURE.md).

---

## 2. Two body shapes

The API returns one of two error shapes depending on where the failure originated.
A client that wants uniform handling should read `detail` first and treat `error` as an
optional machine-readable discriminator.

### 2.1 Domain exceptions — `{ "error", "detail" }`

Raised by the service layer and mapped by the exception handlers in
[app/main.py](../../app/main.py):

```json
{
  "error": "ActiveInstanceException",
  "detail": "Instance 1 is RUNNING and cannot be deleted. Stop it first."
}
```

| Exception | Status | `error` value | Raised by |
|---|---|---|---|
| `ActiveInstanceException` | `409` | `ActiveInstanceException` | `delete_instance()` on a RUNNING instance |
| `NotFoundException` | `404` | `NotFound` | `get_instance()`, `get_client()`, unknown `managerId` |
| `ForbiddenException` | `403` | `Forbidden` | Reserved for service-layer access checks |
| `ValidationException` | `400` | `ValidationError` | `create_client()` when `managerId` is not a `CLIENT_MANAGER` |

Definitions: [app/core/exceptions.py](../../app/core/exceptions.py).

### 2.2 `HTTPException` — `{ "detail" }`

Raised directly in the auth dependencies and the alert controller:

```json
{ "detail": "CLIENT_MANAGER can only access clients assigned to them" }
```

| Situation | Status | `detail` |
|---|---|---|
| Bad email or password | `401` | `Invalid email or password` |
| No `Authorization` header | `401` | `Not authenticated. Provide a Bearer token.` |
| Expired token | `401` | `Token has expired` |
| Malformed token | `401` | `Invalid token` |
| Member deleted after issuance | `401` | `Member no longer exists` |
| Non-ADMIN calls `POST /api/clients` | `403` | `ADMIN role required` |
| Manager touches another manager's client | `403` | `CLIENT_MANAGER can only access clients assigned to them` |
| Unknown alert id | `404` | `Alert {id} not found` |

The split is a known inconsistency: unknown **instance** and **client** ids produce the
`{error, detail}` shape, while an unknown **alert** id produces `{detail}` only, because
the alert controller raises `HTTPException` before reaching the service. Both are `404`
with a human-readable `detail`.

### 2.3 Schema validation — FastAPI `422`

```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["body", "cpuUsage"],
      "msg": "Input should be less than or equal to 100",
      "input": 150
    }
  ]
}
```

Triggered before any application code runs — an unknown enum value, `cpuUsage` outside
`0–100`, `size` above `100`, `page` below `1`, a missing required field, or a malformed
date in `dateFrom` / `dateTo`.

---

## 3. Errors by endpoint

| Endpoint | Possible failures |
|---|---|
| `POST /api/auth/login` | `401` bad credentials · `422` malformed email |
| `POST /api/instances` | `401` · `403` other manager's client · `404` unknown `clientId` · `422` field validation |
| `GET /api/instances` | `401` · `422` bad `page`/`size`/enum |
| `GET /api/instances/{id}` | `401` · `403` · `404` |
| `PATCH /api/instances/{id}/status` | `401` · `403` · `404` · `422` `cpuUsage` out of range |
| `DELETE /api/instances/{id}` | `401` · `403` · `404` · **`409` instance is RUNNING** |
| `GET /api/instances/{id}/diagnosis` | `401` · `403` · `404` |
| `GET /api/monitor/warnings` · `/errors` · `/long-stopped` | `401` · `422` bad `page`/`size` |
| `GET /api/monitor/report` | `401` |
| `GET /api/alerts` | `401` · `422` bad `page`/`size`/enum or date |
| `PATCH /api/alerts/{id}/resolve` | `401` · `403` · `404` |
| `POST /api/clients` | `401` · `403` non-ADMIN · `404` unknown `managerId` · `400` `managerId` is not a CLIENT_MANAGER · `422` |
| `GET /api/clients` | `401` · `422` bad `page`/`size` |
| `GET /api/clients/{id}/*` | `401` · `403` · `404` · `422` bad `page`/`size` on `/instances` |

Note that `403` is returned — not `404` — when a `CLIENT_MANAGER` requests another
manager's resource. The resource is confirmed to exist. That is an accepted trade-off
for an internal tool where instance ids are not secret; see
[../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md).

---

## 4. Related

| Document | Why |
|---|---|
| [ENDPOINTS.md](ENDPOINTS.md) | Success responses for the same endpoints |
| [../business-rules/INSTANCE_LIFECYCLE.md](../business-rules/INSTANCE_LIFECYCLE.md) | Why `409` exists |
| [../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md) | Why `403` is chosen over `404` |
