# Testing

The automated functional suite for the API — what it covers and how to run it. The tests
themselves live in [../../tests/](../../tests/).

| Document | Contents |
|---|---|
| [FUNCTIONAL_TESTS.md](FUNCTIONAL_TESTS.md) | Test approach, fixtures and isolation, the suite catalogue, endpoint coverage, deliberate gaps |
| [RUNNING_TESTS.md](RUNNING_TESTS.md) | Install, run, select individual tests, read a failure, troubleshooting |

## The short version

```bash
pip install -r requirements-dev.txt
pytest -q            # 104 passed
```

Every test drives the API over HTTP against a fresh in-memory database seeded with the
demo data, so expected values are exact — `$2,100` total monthly cost, warnings on
instances `1, 4, 11, 14`, and so on. Nothing is mocked except the Anthropic call, which
means the suite needs no API key, no network, and no running server.

The same numbers appear in [../demo/SEED_DATA.md](../demo/SEED_DATA.md) and
[../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md); the tests are what keeps those
documents from going stale.

## Related

| Document | Why |
|---|---|
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | The contract the tests assert |
| [../api/ERRORS.md](../api/ERRORS.md) | The failure status codes and body shapes asserted on |
| [../business-rules/](../business-rules/README.md) | The rules each test case pins down |
| [../demo/SEED_DATA.md](../demo/SEED_DATA.md) | The fixed data every expectation is built from |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | The manual equivalent of this suite |
| [../contributing/COMMITS.md](../contributing/COMMITS.md) | The `test:` commit prefix |
