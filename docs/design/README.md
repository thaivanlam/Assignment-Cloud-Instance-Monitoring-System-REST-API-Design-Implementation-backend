# Design

How the system is put together — data model, application layering, and the design of the
AI-assisted feature.

| Document | Contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | MVC layering, request flow, module responsibilities, configuration |
| [ERD.md](ERD.md) | Entity relationship diagram, relationships, schema design notes |
| [LLM_FEATURE.md](LLM_FEATURE.md) | `GET /api/instances/{id}/diagnosis` — prompt design, execution paths, fallback |

## Reading order

1. [ERD.md](ERD.md) — the five tables everything else operates on.
2. [ARCHITECTURE.md](ARCHITECTURE.md) — how a request travels from router to service to model.
3. [LLM_FEATURE.md](LLM_FEATURE.md) — the one feature with an external dependency.

## Related

| Document | Why |
|---|---|
| [../business-rules/](../business-rules/README.md) | The logic that lives in the service layer |
| [../api/](../api/README.md) | The contract the controllers expose |
| [../team/MEMBER_C.md](../team/MEMBER_C.md) | Assignment scope breakdown |
