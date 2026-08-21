# Authentication

Every endpoint except `GET /` and `POST /api/auth/login` requires a JWT Bearer token.

---

## 1. Login

```http
POST /api/auth/login
Content-Type: application/json

{ "email": "admin@techvalley.vn", "password": "admin123!" }
```

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "tokenType": "bearer",
  "role": "ADMIN",
  "name": "TechValley Admin"
}
```

`role` and `name` are returned alongside the token so a client can render the current
user without a second round trip.

Wrong email or wrong password both return the same `401` with
`{"detail": "Invalid email or password"}` — the message does not reveal which half was
wrong, so the endpoint cannot be used to enumerate accounts.

Credentials for the seeded accounts: [../demo/ACCOUNTS.md](../demo/ACCOUNTS.md).

---

## 2. Sending the token

```http
Authorization: Bearer <accessToken>
```

| Property | Value |
|---|---|
| Algorithm | `HS256` |
| Signing key | `SECRET_KEY` from `.env` |
| Claims | `sub` (member id, as string), `email`, `role`, `exp` |
| Lifetime | `ACCESS_TOKEN_EXPIRE_MINUTES` — default **120 minutes** |
| Scheme | `HTTPBearer(auto_error=False)` |

`auto_error=False` is deliberate: FastAPI's default would emit a generic
`{"detail": "Not authenticated"}`, whereas the dependency in
[app/core/deps.py](../../app/core/deps.py) raises its own `401` telling the caller
exactly what is missing.

There is no refresh-token endpoint. When a token expires, log in again.

---

## 3. Authorizing in Swagger UI

1. Open `http://127.0.0.1:8000/docs`.
2. Expand `POST /api/auth/login`, click **Try it out**, submit one of the demo accounts.
3. Copy the `accessToken` value from the response body.
4. Click **Authorize** (top right), paste the token, confirm.

Every subsequent **Try it out** call carries the header automatically. Switching users
means repeating steps 2–4 with different credentials — useful for demonstrating the
ADMIN vs CLIENT_MANAGER scoping described in
[../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md).

---

## 4. Password storage

Passwords are stored as salted **PBKDF2-SHA256** hashes
([app/core/security.py](../../app/core/security.py)). The plaintext exists only inside
the login request body and is never logged, returned, or written to the database.

---

## 5. Token failure modes

All four return `401` with an `HTTPException` body — see [ERRORS.md](ERRORS.md).

| Condition | `detail` |
|---|---|
| No `Authorization` header | `Not authenticated. Provide a Bearer token.` |
| `exp` in the past | `Token has expired` |
| Malformed token or bad signature | `Invalid token` |
| Member row deleted after the token was issued | `Member no longer exists` |

The last case matters because the token is stateless: the member is re-loaded from the
database on every request, so revoking access is a matter of deleting the member rather
than waiting for expiry.

---

## 6. Related

| Document | Why |
|---|---|
| [../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md) | What each role is allowed to see and do once authenticated |
| [../demo/ACCOUNTS.md](../demo/ACCOUNTS.md) | Seeded credentials |
| [ERRORS.md](ERRORS.md) | Full error body reference |
