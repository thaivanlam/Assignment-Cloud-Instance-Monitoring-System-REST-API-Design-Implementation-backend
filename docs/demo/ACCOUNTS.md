# Demo Accounts

Three members are created by the seed on first startup
([app/seed.py](../../app/seed.py)). These are demo credentials for a local SQLite
database — they are not secrets and are intentionally checked in.

---

## 1. Credentials

| Role | Email | Password | Name | Sees |
|---|---|---|---|---|
| `ADMIN` | `admin@techvalley.vn` | `admin123!` | TechValley Admin | All 10 clients and all 15 instances |
| `CLIENT_MANAGER` | `lam@techvalley.vn` | `manager123!` | Thai Van Lam | Clients **1–5** only |
| `CLIENT_MANAGER` | `minh@techvalley.vn` | `manager123!` | Nguyen Minh | Clients **6–10** only |

Two managers with a clean 5/5 split exist so that role scoping can be demonstrated in
both directions: each manager sees exactly half the data, and either one can be used to
trigger a `403` against the other's clients.

---

## 2. Client ownership

| Client id | Client | Plan | Manager |
|---|---|---|---|
| 1 | VinaSoft | PREMIUM | lam |
| 2 | Hanoi Logistics | STANDARD | lam |
| 3 | Saigon Retail | BASIC | lam |
| 4 | Mekong Foods | STANDARD | lam |
| 5 | DaNang Media | BASIC | lam |
| 6 | VN FinTech | PREMIUM | minh |
| 7 | EduViet | STANDARD | minh |
| 8 | GreenEnergy VN | BASIC | minh |
| 9 | HealthPlus | PREMIUM | minh |
| 10 | TravelGo | STANDARD | minh |

Full instance inventory: [SEED_DATA.md](SEED_DATA.md).

---

## 3. Authenticating

### Swagger UI

1. Open `http://127.0.0.1:8000/docs`.
2. `POST /api/auth/login` → **Try it out** → submit one of the accounts above.
3. Copy `accessToken` from the response.
4. **Authorize** (top right) → paste → confirm.

To switch users, repeat steps 2–4 with different credentials.

### curl

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@techvalley.vn","password":"admin123!"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['accessToken'])")

curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/monitor/report
```

Tokens last **120 minutes**. When one expires you get
`401 {"detail": "Token has expired"}` — log in again.

---

## 4. Passwords are hashed

The seed stores salted PBKDF2-SHA256 hashes, not the plaintext above
([app/core/security.py](../../app/core/security.py)). Reading `monitoring.db` directly
will not reveal the passwords.

---

## 5. Reseeding

`seed()` is idempotent — it returns immediately if any member already exists, so
restarting the server never duplicates data or resets a password you changed.

To get a clean database: stop the server, delete `monitoring.db`, restart.

---

## 6. Related

| Document | Why |
|---|---|
| [SEED_DATA.md](SEED_DATA.md) | Instances and cost snapshots these accounts can see |
| [WALKTHROUGH.md](WALKTHROUGH.md) | Where to go after logging in |
| [../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md) | What each role is permitted to do |
| [../api/AUTHENTICATION.md](../api/AUTHENTICATION.md) | JWT claims, lifetime, failure modes |
