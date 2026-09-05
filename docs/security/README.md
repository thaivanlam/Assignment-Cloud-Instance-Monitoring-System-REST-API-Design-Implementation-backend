# Security

Findings on injection, information disclosure and session integrity in `app/` — what an
attacker can reach, how it was reproduced, and what closing it would take.

| Document | Contents |
|---|---|
| [SECURITY_BUGS.md](SECURITY_BUGS.md) | 15 reproduced findings ranked by what an attacker gains, each with evidence and a fix; a **Status** column saying which are closed — none yet; a suggested order of work; what was checked and found sound; the reproduction method |

## The short version

Everything in `SECURITY_BUGS.md` is a security defect, not a functional one — all 128
tests pass and every endpoint returns the answer its documentation promises. Two findings
are rated critical, and both are the same failure in different clothes: **authentication
can be bypassed entirely without touching the API's logic.**

- **SEC-01** — the default `SECRET_KEY` is a literal in [config.py](../../app/config.py)
  and in [.env.example](../../.env.example), so anyone who can read this repository can
  sign a token. A forged `ADMIN` token was accepted at an `ADMIN`-only endpoint, and
  because nothing requires the `exp` claim, a forged token can be made never to expire.
- **SEC-02** — three working accounts and their passwords are embedded in the FastAPI
  description, which `/openapi.json` and `/docs` serve to anyone, unauthenticated. SEC-01
  needs an attacker to read the source; this one needs them to open the front page.
- **SEC-03** — a real `ADMIN` JWT is committed inside
  [02_login_admin.png](../screenshots/02_login_admin.png). It is expired, but its signature
  verifies under the default key, which makes it a known-plaintext pair an attacker can
  work against offline.
- **SEC-04** — there is no logout and no revocation. A token cannot be stopped before its
  expiry, on any device; **SEC-08** is why — the token carries no `jti` or `iat`, so there
  is nothing to name in a denylist. These two are the session finding the review was asked
  for, and they have to be fixed in that order.
- **SEC-05** — login accepts unlimited guesses with no lockout and no log line; 25 wrong
  passwords in a row changed nothing. **SEC-09** pairs with it: a login against a known
  address takes 45.5 ms and one against an unknown address 3.3 ms, so the clock says which
  accounts exist.
- **SEC-06** — scoped endpoints answer `403` for a record that exists and `404` for one
  that does not, so walking the id space maps another client's estate. The split is
  documented as deliberate in
  [../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md), which is why it
  is recorded rather than changed on sight.
- **SEC-07** — `instanceName` reaches the diagnosis prompt as unfenced text, so a client
  manager can write instructions the model reads as its own. What is at risk is the
  integrity of an incident diagnosis, not the database
  ([../design/LLM_FEATURE.md](../design/LLM_FEATURE.md)).

The other findings are smaller: no security headers (**SEC-10**), a `500` where a `401`
belongs (**SEC-11**), an internal class name in an error body (**SEC-12**, required by the
assignment), unvalidated free text that only becomes XSS in a consumer that renders it
(**SEC-13**), and two notes on token lifetime and storage (**SEC-14**, **SEC-15**).

Two things the review looked hard at and found sound, recorded as carefully as the
defects: **SQL injection is not present and is structurally prevented** — every query is
ORM with bound parameters, and the one caller-named column goes through a whitelist — and
**no stack trace reaches a client**. Password hashing and the fact that the database, not
the token, decides a caller's role are correct as written. The detail is in
[§ What is not broken](SECURITY_BUGS.md#what-is-not-broken).

Every finding was **reproduced** against the seeded API through the same `TestClient`
harness the test suite uses, with the application code unmodified; the method is at the end
of the document so any result can be re-run. None are fixed yet — this document is the
register, and the order to work through them is at
[§ Where to start](SECURITY_BUGS.md#where-to-start).

## Related

| Document | Why |
|---|---|
| [../api/AUTHENTICATION.md](../api/AUTHENTICATION.md) | The token contract behind SEC-04, SEC-08, SEC-14 and SEC-15 |
| [../business-rules/AUTHORIZATION.md](../business-rules/AUTHORIZATION.md) | The role scoping that holds, and the `403`/`404` split SEC-06 argues with |
| [../api/ERRORS.md](../api/ERRORS.md) | The error bodies of SEC-11 and SEC-12 |
| [../design/LLM_FEATURE.md](../design/LLM_FEATURE.md) | The diagnosis prompt SEC-07 injects into |
| [../operations/CONFIGURATION.md](../operations/CONFIGURATION.md) | Generating and rotating the key SEC-01 is about |
| [../demo/ACCOUNTS.md](../demo/ACCOUNTS.md) | The seeded credentials SEC-02 publishes |
| [../performance/README.md](../performance/README.md) | The sibling register — same repository, same method, different failure mode |
| [../testing/FUNCTIONAL_TESTS.md](../testing/FUNCTIONAL_TESTS.md) | Why a passing suite catches none of this |
| [../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md) | Keeping this document current when a finding is closed |
