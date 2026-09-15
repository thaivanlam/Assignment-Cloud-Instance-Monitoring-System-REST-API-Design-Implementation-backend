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
wrong, so the endpoint cannot be used to enumerate accounts. Every failure is logged at
`WARNING` with the email and the client address.

Credentials for the seeded accounts: [../demo/ACCOUNTS.md](../demo/ACCOUNTS.md).

---

## 2. Login rate limit

Failed logins are counted in fixed windows, and a caller over either limit is refused
**before** the password is checked
([app/core/rate_limit.py](../../app/core/rate_limit.py)):

| Counted per | Limit | Setting |
|---|---|---|
| Target account (email, case-insensitive) | 10 failures | `LOGIN_MAX_FAILURES_PER_ACCOUNT` |
| Client address | 50 failures | `LOGIN_MAX_FAILURES_PER_IP` |
| Window | 15 minutes from the first attempt a counter records | `LOGIN_WINDOW_SECONDS` = `900` |

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 812

{ "detail": "Too many failed login attempts. Try again later." }
```

`Retry-After` is the number of seconds until the window that tripped ends. Once it has,
the counter is gone and the account logs in normally.

| Rule | Why |
|---|---|
| The account limit applies even to the right password | Otherwise the limit would only stop wrong guesses, which is to say it would tell an attacker when they had guessed right |
| A refused request never runs PBKDF2 | Each check costs ~45 ms of CPU; refusing first removes the lever that let a flood of logins starve every other endpoint |
| A successful login clears the account counter | A user who mistyped a few times starts from zero once they are in |
| A successful login does **not** clear the address counter | Logging in to one's own account must not wipe the failures an address ran up against other accounts; it only gives back its own attempt, so many people behind one office address logging in correctly never reach the limit |
| The window is fixed at the first failure and never extended | A caller that keeps hitting the limit cannot keep an account locked indefinitely |
| An attempt is counted before it is checked | Counting after a failure would let a burst of concurrent guesses all pass the check before any was recorded |

**The trade-off.** A per-account limit lets anyone who knows an email address lock that
account out for up to 15 minutes by failing on purpose. That is accepted: the account is
never locked for longer than one window, and the alternative — no per-account limit —
leaves a distributed attacker free to guess one account's password from many addresses.

**Behind a reverse proxy** the client address is the proxy's unless uvicorn runs with
`--proxy-headers` — every user would otherwise share one address counter
([../operations/DEPLOYMENT.md § 5](../operations/DEPLOYMENT.md#5-launch--a-single-server)).

---

## 3. Sending the token

```http
Authorization: Bearer <accessToken>
```

| Property | Value |
|---|---|
| Algorithm | `HS256` |
| Signing key | `SECRET_KEY` from `.env` |
| Claims | `sub` (member id, as string), `email`, `role`, `iat`, `exp`, `jti` (a random 32-hex-digit id) |
| Required on decode | `exp` and `jti` — a token missing either is `401 Invalid token` |
| Lifetime | `ACCESS_TOKEN_EXPIRE_MINUTES` — default **120 minutes** |
| Scheme | `HTTPBearer(auto_error=False)` |

`auto_error=False` is deliberate: FastAPI's default would emit a generic
`{"detail": "Not authenticated"}`, whereas the dependency in
[app/core/deps.py](../../app/core/deps.py) raises its own `401` telling the caller
exactly what is missing.

`jti` is required rather than optional because a token without one could never be revoked
(§ 4), and `exp` because a revocation lasts exactly as long as the token would. Tokens
issued before these claims existed are rejected, so upgrading a running deployment signs
everyone out once.

There is no refresh-token endpoint. When a token expires, log in again.

---

## 4. Logout and revocation

```http
POST /api/auth/logout
Authorization: Bearer <accessToken>
```

`204 No Content`. From then on the same token answers
`401 {"detail": "Token has been revoked"}` on every endpoint, logout included.

| Property | Behaviour |
|---|---|
| Scope | Only the token sent. The member's other sessions — another browser, another device — stay valid |
| Storage | The token's `jti` in a denylist ([app/core/revocation.py](../../app/core/revocation.py)); nothing is stored when a token is issued |
| Lifetime of the entry | Until the token's own `exp`. After that the signature check rejects the token anyway, so the entry expires with it and the denylist never outgrows the tokens revoked within one token lifetime |
| Cost per request | One key lookup, done before the member is loaded — a revoked token costs no database query |

**Revoking every session of one member** — the password-change or compromise case — is not
provided. The ways to do it today are deleting the member (§ 7) or rotating `SECRET_KEY`,
which signs out everyone.

### Where the denylist and the counters live

Both are kept in the store chosen by `REDIS_URL`
([../operations/CONFIGURATION.md § 6](../operations/CONFIGURATION.md#6-redis_url--shared-state)):

| `REDIS_URL` | Store | Correct for |
|---|---|---|
| empty (default) | Process memory | One worker process — the configuration this project runs in |
| `redis://…` | Redis, shared by every process | Several workers, several servers, or serverless instances |

With process memory and more than one worker, each worker keeps its own denylist and
counters: a logout reaches only the worker that served it, and each worker allows its own
10 failures.

If Redis becomes unreachable the API **fails open** — logins are not limited, revoked tokens
are accepted again, and each failed Redis call logs a warning — rather than refusing every
request. The protection returns when Redis does; nothing already revoked is lost unless
Redis itself lost its data.

---

## 5. Authorizing in Swagger UI

1. Open `http://127.0.0.1:8000/docs`.
2. Expand `POST /api/auth/login`, click **Try it out**, submit one of the demo accounts.
3. Copy the `accessToken` value from the response body.
4. Click **Authorize** (top right), paste the token, confirm.

Every subsequent **Try it out** call carries the header automatically. Switching users
means repeating steps 2–4 with different credentials — useful for demonstrating the
ADMIN vs CLIENT_MANAGER scoping described in
[../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md).

The **Logout** button in Swagger's Authorize dialog only forgets the token in the browser;
it does not call the API. To revoke the token, execute `POST /api/auth/logout` first.

---

## 6. Password storage

Passwords are stored as salted **PBKDF2-SHA256** hashes
([app/core/security.py](../../app/core/security.py)). The plaintext exists only inside
the login request body and is never logged, returned, or written to the database.

---

## 7. Token failure modes

All five return `401` with an `HTTPException` body — see [ERRORS.md](ERRORS.md).

| Condition | `detail` |
|---|---|
| No `Authorization` header | `Not authenticated. Provide a Bearer token.` |
| `exp` in the past | `Token has expired` |
| Malformed token, bad signature, or no `exp` / `jti` claim | `Invalid token` |
| Token revoked by `POST /api/auth/logout` | `Token has been revoked` |
| Member row deleted after the token was issued | `Member no longer exists` |

The last case matters because the member is re-loaded from the database on every request,
so deleting the member revokes every token they hold at once, without waiting for expiry.

---

## 8. Related

| Document | Why |
|---|---|
| [../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md) | What each role is allowed to see and do once authenticated |
| [../demo/ACCOUNTS.md](../demo/ACCOUNTS.md) | Seeded credentials |
| [ERRORS.md](ERRORS.md) | Full error body reference |
| [../operations/CONFIGURATION.md](../operations/CONFIGURATION.md) | The rate-limit settings and `REDIS_URL` |
| [../security/SECURITY_BUGS.md](../security/SECURITY_BUGS.md) | SEC-04, SEC-05 and SEC-08 — the findings §§ 2–4 close |
