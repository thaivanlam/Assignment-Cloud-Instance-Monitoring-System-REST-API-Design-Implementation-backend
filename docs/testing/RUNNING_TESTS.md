# Running the Tests

How to install, run, and read the automated suite. What each test asserts is in
[FUNCTIONAL_TESTS.md](FUNCTIONAL_TESTS.md).

All commands are run from the repository root.

---

## 1. Install

The test dependencies are separate from the runtime ones.

```powershell
# Windows / PowerShell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

`requirements-dev.txt` pulls in `requirements.txt`, so this one command installs
everything. Playwright is included for the screenshot script and is not needed by the
tests — you can skip `playwright install`.

No `.env`, no API key, and no running server are required. The suite starts its own
application instance in-process.

---

## 2. Run everything

```bash
pytest -q
```

```
........................................................................ [ 58%]
...................................................                      [100%]
123 passed in 20.08s
```

Expect **seconds on an idle machine, up to about a minute on a busy one**. Every test
builds and seeds its own database and logs in three times, and each login verifies a
password at 260,000 PBKDF2 iterations — that deliberate cost is most of the runtime.

If `pytest` is not on your `PATH`, use `python -m pytest` — same arguments.

---

## 3. Run part of the suite

| Goal | Command |
|---|---|
| One file | `pytest tests/test_clients.py` |
| One test | `pytest tests/test_clients.py::test_forecast_counts_only_running_instances` |
| Everything matching a word | `pytest -k cost` |
| A boolean match | `pytest -k "cost and not forecast"` |
| One parametrized case | `pytest "tests/test_instances.py::test_list_instances_filters[region]"` |
| List cases without running | `pytest --collect-only -q` |

Quote any node id containing `[` `]` — PowerShell and bash both treat brackets as
special characters otherwise.

---

## 4. Useful flags

| Flag | Effect |
|---|---|
| `-q` | One character per test instead of one line |
| `-v` | Full test name per line |
| `-x` | Stop at the first failure |
| `--lf` | Re-run only the tests that failed last time |
| `--ff` | Run last failures first, then the rest |
| `-ra` | Summary of every non-passing outcome at the end |
| `--durations=10` | Ten slowest tests — start here if the suite feels slow |
| `-s` | Show `print()` output (pytest captures it by default) |
| `-W error` | Turn warnings into failures |

A useful combination while fixing a regression:

```bash
pytest -x --lf -v
```

---

## 5. Reading a failure

pytest prints the failing assertion with both sides expanded:

```
    def test_forecast_counts_only_running_instances(api, auth_headers):
        ...
>       assert body["forecastCost"] == 500.0
E       assert 620.0 == 500.0

tests/test_clients.py:203: AssertionError
```

Work through it in this order:

1. **Is the new behaviour intended?** If yes, the test and the document describing that
   rule change together, in the same commit —
   [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md).
2. **Did the seed change?** Most expected values come from the demo data. A change to
   [app/seed.py](../../app/seed.py) breaks many tests at once and also invalidates
   [../demo/SEED_DATA.md](../demo/SEED_DATA.md) and
   [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md).
3. **Only one test failing?** Read the rule it pins in
   [FUNCTIONAL_TESTS.md](FUNCTIONAL_TESTS.md) §4 before changing either side.

Then re-run just that test with `-v` until it passes, and finish with a full `pytest -q`.

---

## 6. What running the tests does *not* touch

| | |
|---|---|
| `monitoring.db` | Never opened. Each test builds its own in-memory SQLite database and the `get_db` dependency is overridden to use it. |
| The network | Never used. The Anthropic call is stubbed — [FUNCTIONAL_TESTS.md](FUNCTIONAL_TESTS.md) §6. |
| `.env` | Read for settings if present, but no value in it is required. |
| A running server | Not needed. Do not start `uvicorn` first. |

So it is safe to run the suite at any time, including while the demo server is running.

---

## 7. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: No module named 'app'` | Running from the wrong directory. Run `pytest` from the repository root, not from `tests/`. |
| `ModuleNotFoundError: No module named 'fastapi'` / `'pytest'` | The virtualenv is not active, or only `requirements.txt` was installed. Activate it and install `requirements-dev.txt`. |
| `no tests ran` | A typo in `-k` or in the node id, or brackets that the shell ate — quote the node id. |
| `InsecureKeyLengthWarning: The HMAC key is 16 bytes long` | `SECRET_KEY` in `.env` is shorter than the 32 bytes PyJWT recommends for HS256. Harmless for the demo; set a longer `SECRET_KEY` to silence it. |
| Tests pass alone but fail together | Genuine state leakage — but note each test gets a fresh database, so suspect module-level state or a monkeypatch that was not undone. |
| The suite takes several minutes | Check `--durations=10`. Setup time that climbs as the run progresses means a fixture is leaking resources; a test reaching the real Anthropic API shows up as seconds on that one test. |

---

## 8. Before you commit

```bash
pytest -q
```

A green suite is expected on every commit. If a change alters behaviour on purpose,
update the test and the document that describes the rule in the *same* commit; use the
`test:` prefix only when nothing outside `tests/` changes —
[../contributing/COMMITS.md](../contributing/COMMITS.md).

---

## 9. Related

| Document | Why |
|---|---|
| [FUNCTIONAL_TESTS.md](FUNCTIONAL_TESTS.md) | What each suite asserts and why |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | The same behaviour verified by hand in Swagger UI |
| [../contributing/COMMITS.md](../contributing/COMMITS.md) | Commit prefixes, including `test:` |
| [../../README.md](../../README.md) | Project quick start |
