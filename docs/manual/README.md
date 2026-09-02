# User Manual

End-user documentation for the people who operate the system — administrators, client
managers and on-call engineers. No knowledge of the code is assumed.

| Document | Contents |
|---|---|
| [USER_MANUAL.md](USER_MANUAL.md) | Signing in, finding and updating instances, running the monitoring checks, working the alert queue, cost, forecast, SLA, diagnosis, an error-message reference and an FAQ |

## Which document do you want?

| If you want to… | Read |
|---|---|
| Learn to use the system, task by task | [USER_MANUAL.md](USER_MANUAL.md) |
| Follow a scripted tour with exact expected numbers | [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) |
| Look up one endpoint's fields | [../api/ENDPOINTS.md](../api/ENDPOINTS.md) |
| Understand *why* a rule is what it is | [../business-rules/README.md](../business-rules/README.md) |
| Fix a server that will not start | [../operations/RUNBOOKS.md](../operations/RUNBOOKS.md) |

The manual and the walkthrough overlap on purpose and are not the same thing: the manual
is organised by **what you are trying to do** and is meant to be read in parts, while the
[walkthrough](../demo/WALKTHROUGH.md) is one sequence run start to finish against the
seeded data, with every expected number stated so you can tell whether the system is
behaving.

## Keeping it current

The manual describes observable behaviour, so a change to a route, a field, a status code
or an error message makes part of it wrong. It changes in the **same commit** as that
behaviour, like every other document here —
[../contributing/DOCUMENTATION.md](../contributing/DOCUMENTATION.md).

## Related

| Document | Why |
|---|---|
| [../api/README.md](../api/README.md) | The reference behind everything the manual shows |
| [../api/ERRORS.md](../api/ERRORS.md) | The complete version of the manual's error table |
| [../demo/ACCOUNTS.md](../demo/ACCOUNTS.md) | The accounts the manual signs in with |
| [../requirements/USE_CASES.md](../requirements/USE_CASES.md) | The same tasks as specified scenarios, with acceptance criteria |
| [../operations/README.md](../operations/README.md) | Running the system, rather than using it |
