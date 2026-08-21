# Demo

Everything needed to run the API and exercise it against realistic data — credentials,
what the seed creates, and a step-by-step walkthrough.

| Document | Contents |
|---|---|
| [ACCOUNTS.md](ACCOUNTS.md) | Demo login credentials, which clients each manager owns, how to authenticate |
| [SEED_DATA.md](SEED_DATA.md) | The 3 members, 10 clients, 15 instances, and cost snapshots created on first run |
| [WALKTHROUGH.md](WALKTHROUGH.md) | Ordered demo script — curl and Swagger — with the captured screenshots |

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger UI: **http://127.0.0.1:8000/docs**

`monitoring.db` is created and seeded automatically on first startup. Log in with
`admin@techvalley.vn` / `admin123!` and start from [WALKTHROUGH.md](WALKTHROUGH.md).

To start over from a clean database, stop the server, delete `monitoring.db`, and
restart — the seed runs again.

## Related

| Document | Why |
|---|---|
| [../api/AUTHENTICATION.md](../api/AUTHENTICATION.md) | Token mechanics behind the login step |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | Reference for every call in the walkthrough |
| [../business-rules/](../business-rules/README.md) | What the walkthrough is demonstrating |
| [../testing/](../testing/README.md) | The automated equivalent of the walkthrough — it asserts the same figures |
| [screenshots/](../screenshots/README.md) | Captured Swagger UI responses |
