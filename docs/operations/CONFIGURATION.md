# Configuration and keys

Every setting the application reads, where it comes from, how to generate the two secrets,
and what breaks when one of them changes.

The settings themselves are declared once, as Pydantic `BaseSettings` fields in
[../../app/config.py](../../app/config.py). This document is the operational view of that
file; the design view is
[../design/ARCHITECTURE.md § 6](../design/ARCHITECTURE.md#6-configuration).

---

## 1. Where settings come from

Three sources, highest priority first:

| Priority | Source | Typical use |
|---|---|---|
| 1 | **Environment variable** | Deployment — systemd `EnvironmentFile`, a container's env, `vercel env add` |
| 2 | **`.env`** in the working directory | Local development; ignored by git |
| 3 | **The default in `app/config.py`** | Everything unset — the app runs with no configuration at all |

An environment variable wins over `.env`, so a deployment can override a committed
development value without editing a file:

```bash
DATABASE_URL="sqlite:///./other.db" uvicorn app.main:app     # .env is overridden
```

**Settings are resolved at import time.** `settings = Settings()` runs when `app.config`
is first imported, and `UNIT_PRICES` / `SLA_THRESHOLDS` are built from it immediately
after. Editing `.env` therefore changes nothing until the process restarts — there is no
reload endpoint and no runtime mutation path.

`.env` is listed in [../../.gitignore](../../.gitignore); the committed template is
[../../.env.example](../../.env.example). Never commit a real key: the template exists so
that the file with the secrets in it never has to be.

---

## 2. Every setting

| Setting | Default | What it controls | Change it when |
|---|---|---|---|
| `APP_NAME` | `TechValley Cloud Instance Monitoring System` | Swagger title, `GET /` body | Rebranding a deployment |
| `SECRET_KEY` | `change-me-to-a-long-random-string` | JWT signing key | **Always, before any real deployment** — § 3 |
| `ALGORITHM` | `HS256` | JWT signature algorithm | Practically never |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `120` | Token lifetime | Shorter for a shared demo, longer for a long walkthrough |
| `DATABASE_URL` | `sqlite:///./monitoring.db` | Which database is opened, and which pool — § 5 | Moving off the local file |
| `ANTHROPIC_API_KEY` | `""` (empty) | The LLM diagnosis path — § 4 | Enabling real diagnoses |
| `CPU_WARNING_THRESHOLD` | `80.0` | The CPU % above which a scan raises `CPU_HIGH` | § 6 |
| `LONG_STOPPED_HOURS` | `48` | How long `STOPPED` counts as long-stopped | § 6 |
| `PRICE_SMALL` / `PRICE_MEDIUM` / `PRICE_LARGE` | `50` / `120` / `250` | Monthly unit price per instance type | § 6 |
| `SLA_PREMIUM` / `SLA_STANDARD` / `SLA_BASIC` | `99.9` / `99.0` / `95.0` | Uptime target per contract plan | § 6 |

Unknown variables are ignored (`extra="ignore"`), so a typo in a name is silent — the app
starts and uses the default. § 7 shows how to read back what it actually loaded.

---

## 3. `SECRET_KEY`

The HMAC key every access token is signed with. A token is accepted by any process holding
the same key and rejected by any process that does not — that single fact explains every
operational consequence below.

**Generate one:**

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then set it — in `.env` for local work, as an environment variable everywhere else:

```bash
SECRET_KEY=<the generated value>
```

| Situation | Consequence |
|---|---|
| Left at the default | The key is published in this repository. Anyone can sign a token claiming `role: ADMIN` and read every client. **Not acceptable outside a laptop.** |
| Shorter than 32 bytes | PyJWT logs `InsecureKeyLengthWarning: The HMAC key is 16 bytes long`. Harmless for a demo, but the generator above gives 48 bytes — use it |
| Rotated | **Every token issued before the rotation stops working** and clients get `401` until they log in again. There is no refresh token and no key list, so a rotation is a forced re-login for everyone ([RUNBOOKS.md § R6](RUNBOOKS.md#r6--every-request-returns-401-after-a-restart)) |
| Different per worker/instance | A token minted by one is rejected by the next — every process behind a load balancer needs the *same* value |

Token contents and lifetime: [../api/AUTHENTICATION.md](../api/AUTHENTICATION.md).

---

## 4. `ANTHROPIC_API_KEY`

Optional. It powers exactly one endpoint —
`GET /api/instances/{id}/diagnosis` — and its absence is a **supported configuration**:
[../../app/services/llm_service.py](../../app/services/llm_service.py) catches every
failure and returns a deterministic rule-based diagnosis instead, so the endpoint never
fails and the demo never breaks.

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

Two details that have caused confusion before:

- **The SDK reads the environment variable, not `.env`.** `llm_service` passes the value
  pydantic-settings loaded to `anthropic.Anthropic(api_key=...)` explicitly. If the
  setting is empty it constructs the client with no key and lets the SDK resolve
  credentials itself (`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, or an `ant auth login`
  profile) — so a diagnosis can succeed on a machine where this setting is blank.
- **A wrong key is not an outage.** The call fails, the fallback answers, and the process
  logs one warning line ([RUNBOOKS.md § R11](RUNBOOKS.md#r11--diagnosis-answers-rule-based-when-a-key-is-configured)).

**Which path answered** is in the response itself:

```bash
curl -s "$BASE/api/instances/11/diagnosis" -H "Authorization: Bearer <token>" | grep -o '"source":"[a-z-]*"'
# "source":"llm"          — the provider answered
# "source":"rule-based"   — no key, a rejected key, a network failure, or a timeout
```

The call is bounded at 30 seconds with one retry — a 60-second worst case — and the
database connection is released before it runs
([../performance/PERFORMANCE_BUGS.md § PERF-03](../performance/PERFORMANCE_BUGS.md#perf-03)).
To disable the LLM path deliberately, unset the variable and restart: the endpoint keeps
working, always answering `rule-based`. Prompt and model:
[../design/LLM_FEATURE.md](../design/LLM_FEATURE.md).

---

## 5. `DATABASE_URL`

```bash
DATABASE_URL=sqlite:///./monitoring.db      # relative to the working directory
DATABASE_URL=sqlite:////srv/data/mon.db     # four slashes = absolute path
```

The URL decides more than the file name — it selects the connection pool, and the pool
sizing is only valid for one of them:

| URL | Pool | Sizing applied |
|---|---|---|
| `sqlite:///<path>` | `QueuePool` | `pool_size=20`, `max_overflow=20`, `pool_pre_ping=True` |
| `sqlite:///:memory:`, `sqlite://` | `SingletonThreadPool` | None — passing it would raise `TypeError` at import |

Both SQLite forms also get `check_same_thread=False` and the WAL pragmas. The full
explanation, including why the in-memory guard exists, is
[../design/DATABASE.md](../design/DATABASE.md).

Two operational cautions:

- **In-memory is not a deployment mode.** `sqlite://` gives each connection its own empty
  database; it is used by the test suite with a `StaticPool` and nowhere else.
- **A non-SQLite URL needs its driver installed.** `requirements.txt` ships none, so
  `postgresql://…` fails at import with `ModuleNotFoundError: No module named 'psycopg2'`
  ([RUNBOOKS.md § R5](RUNBOOKS.md#r5--modulenotfounderror-no-module-named-psycopg2)).
  Moving off SQLite is a deliberate change: add the driver, and note that schema creation
  still happens in the startup hook rather than in a migration.

---

## 6. Business thresholds — changing them changes documented numbers

`CPU_WARNING_THRESHOLD`, `LONG_STOPPED_HOURS`, the three prices and the three SLA targets
are configuration, but they are also the numbers the rest of the documentation states as
facts and the test suite asserts exactly.

| Setting | What moves with it |
|---|---|
| `CPU_WARNING_THRESHOLD` | Which instances `GET /api/monitor/warnings` returns, and which `CPU_HIGH` alerts exist — [../business-rules/ALERTING.md](../business-rules/ALERTING.md) |
| `LONG_STOPPED_HOURS` | `GET /api/monitor/long-stopped` and its alerts — same document |
| `PRICE_*` | Every instance's `monthlyCost`, client cost totals and the forecast — [../business-rules/COST.md](../business-rules/COST.md) |
| `SLA_*` | The compliance verdict per plan — [../business-rules/SLA.md](../business-rules/SLA.md) |

Changing one in a *deployment* is fine and takes effect on restart. Changing one in
`app/config.py` is a code change: the 123 tests assert the seeded figures, and
[../demo/SEED_DATA.md](../demo/SEED_DATA.md),
[../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) and the Swagger captures all quote them —
so the document and the captures move in the same commit
([../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md)).

Note also that prices are applied **when an instance is created**; changing a price does
not rewrite the `monthlyCost` already stored on existing rows.

---

## 7. Read back the effective configuration

The fastest way to end an argument about which value is actually in force. It prints what
the process loaded, with the two secrets reduced to a length:

```bash
python -c "
from app.config import settings
d = settings.model_dump()
for k in ('SECRET_KEY', 'ANTHROPIC_API_KEY'):
    d[k] = f'<set, {len(d[k])} chars>' if d[k] else '<empty>'
for k, v in d.items():
    print(f'{k} = {v}')
"
```

```
APP_NAME = TechValley Cloud Instance Monitoring System
SECRET_KEY = <set, 33 chars>
ALGORITHM = HS256
ACCESS_TOKEN_EXPIRE_MINUTES = 120
DATABASE_URL = sqlite:///./monitoring.db
ANTHROPIC_API_KEY = <set, 108 chars>
CPU_WARNING_THRESHOLD = 80.0
...
```

Run it in the same working directory and with the same environment as the server —
otherwise it reads a different `.env` and reports values the server never saw.

---

## 8. Secret hygiene

- `.env` is gitignored. Keep it that way; put deployment secrets in the platform's own
  store (systemd `EnvironmentFile` with `0600`, `vercel env add`, the container's secret
  mount) rather than in the image or the repository.
- Never paste a token or a key into an issue, a screenshot or a changelog entry. The
  Swagger captures in [../screenshots/](../screenshots/README.md) show demo tokens signed
  with the demo key, which is why the demo key must never be a real one.
- The demo passwords in [../demo/ACCOUNTS.md](../demo/ACCOUNTS.md) are published on
  purpose. Any deployment reachable by someone who should not see the data needs those
  accounts changed or removed — the seed creates them on any empty database.
- Rotating `SECRET_KEY` invalidates every issued token (§ 3). Plan it as a brief forced
  re-login, not as a transparent change.

---

## 9. Related

| Document | Why |
|---|---|
| [DEPLOYMENT.md](DEPLOYMENT.md) | Where these values are set for each way of launching |
| [RUNBOOKS.md](RUNBOOKS.md) | The failures a misconfiguration produces, and their fixes |
| [../design/ARCHITECTURE.md](../design/ARCHITECTURE.md) | The settings table from the design side, and import-time resolution |
| [../design/DATABASE.md](../design/DATABASE.md) | What `DATABASE_URL` selects beyond the file name |
| [../design/LLM_FEATURE.md](../design/LLM_FEATURE.md) | The endpoint `ANTHROPIC_API_KEY` enables, and its fallback |
| [../api/AUTHENTICATION.md](../api/AUTHENTICATION.md) | The tokens `SECRET_KEY` signs |
| [../business-rules/README.md](../business-rules/README.md) | The rules the threshold settings parameterise |
| [../demo/ACCOUNTS.md](../demo/ACCOUNTS.md) | The seeded credentials § 8 warns about |
