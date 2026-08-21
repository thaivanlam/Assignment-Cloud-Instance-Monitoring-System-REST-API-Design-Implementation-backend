# API Documentation

Reference for the TechValley Cloud Instance Monitoring REST API — what the endpoints
are, how to call them, and what they return.

| Document | Contents |
|---|---|
| [OVERVIEW.md](OVERVIEW.md) | Base URL, versioning, endpoint map, enumerations, naming conventions |
| [AUTHENTICATION.md](AUTHENTICATION.md) | Login flow, JWT claims and lifetime, Swagger authorization, token failure modes |
| [CONVENTIONS.md](CONVENTIONS.md) | Pagination, filtering, sorting, timestamp format |
| [ERRORS.md](ERRORS.md) | Status codes and the two error body shapes |
| [ENDPOINTS.md](ENDPOINTS.md) | Per-endpoint request/response reference |

## Start here

1. [OVERVIEW.md](OVERVIEW.md) — see the whole surface at a glance.
2. [AUTHENTICATION.md](AUTHENTICATION.md) — get a token; nothing else works without one.
3. [ENDPOINTS.md](ENDPOINTS.md) — look up the call you need.

## Related

| Document | Why |
|---|---|
| [../business-rules/](../business-rules/README.md) | *Why* an endpoint behaves the way it does — thresholds, dedup, pricing, SLA |
| [../demo/](../demo/README.md) | Credentials and seeded data to call these endpoints against |
| [../design/ERD.md](../design/ERD.md) | Field-level data model behind the DTOs |
| [../design/LLM_FEATURE.md](../design/LLM_FEATURE.md) | Design of `GET /api/instances/{id}/diagnosis` |
