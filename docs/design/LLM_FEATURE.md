# LLM Feature — Instance Diagnosis

Design and implementation notes for the AI-assisted feature of the TechValley Cloud
Instance Monitoring System: **automatic incident diagnosis for a cloud instance**.

| Item | Value |
|---|---|
| Endpoint | `GET /api/instances/{id}/diagnosis` |
| Provider / SDK | Anthropic Claude, official `anthropic` Python SDK (`>=0.116.0`) |
| Model | `claude-opus-4-8` |
| Request limits | 30 s timeout, 1 retry — 60 s worst case |
| Service module | [app/services/llm_service.py](../../app/services/llm_service.py) |
| Controller | [app/controllers/instance_controller.py:98-135](../../app/controllers/instance_controller.py#L98-L135) |
| Response DTO | `DiagnosisResponse` in [app/schemas/schemas.py:144-149](../../app/schemas/schemas.py#L144-L149) |

---

## 1. Purpose

When an instance fails, an operator has to correlate the instance metadata (CPU, type,
region, last status change) with its recent alert history and then decide what to do.
This feature automates that first pass: it feeds the same data an engineer would read
into an LLM and returns a short, structured incident write-up — probable causes,
ordered remediation steps, and prevention advice.

The endpoint is designed to be **always available**. If no API credentials are
configured (a demo machine, CI, offline grading), the service degrades to a
deterministic rule-based diagnosis instead of returning an error. The response tells
the caller which path produced the text via the `source` field.

---

## 2. Architecture

```
GET /api/instances/{id}/diagnosis
        │
        ▼
instance_controller.diagnose_instance()
        │  1. load instance (404 if missing)
        │  2. assert_client_access(member, instance.client)   ← JWT + role scoping
        │  3. load 10 most recent alerts (ORDER BY detectedAt DESC)
        │  4. db.close()  ← release the pooled connection before the network call
        ▼
llm_service.diagnose(instance, alerts) -> (text, source)
        │
        ├── _llm_diagnosis()      → Anthropic Messages API      → source = "llm"
        │        └── on any exception (no key, network, quota) ─┐
        │                                                       ▼
        └── _rule_based_diagnosis() → deterministic template  → source = "rule-based"
        │
        ▼
DiagnosisResponse (JSON)
```

**Design decisions**

- **Service-layer isolation.** All LLM concerns live in `llm_service.py`. The
  controller never imports `anthropic`; it only receives `(text, source)`. Swapping
  provider or prompt requires no change to routing, schemas, or business services.
- **Bounded context.** Exactly one instance row plus at most 10 alerts are sent. The
  prompt size is therefore predictable and small (a few hundred tokens), which keeps
  latency and cost stable regardless of how much alert history an instance accumulates.
- **No raw ORM objects in the prompt.** `_build_context()` flattens the entities into
  a plain-text block, so internal IDs, foreign keys, and client PII are never sent to
  the provider.
- **Fail-open, never fail-closed.** A monitoring endpoint that returns 500 because a
  third-party API is down is worse than one that returns a slightly less insightful
  answer. Hence the fallback.
- **Bounded wait, and nothing held during it.** The provider call is capped at 30
  seconds per attempt with a single retry, and the handler returns its database
  connection to the pool before making the call. See § 4.5.

### 2.1 The two execution paths

The controller, authorization, DB queries, and response schema are **identical** in
both paths. They diverge only inside `llm_service.diagnose()`, and the divergence is
reported to the caller through `source`.

#### Path A — API key present (`source: "llm"`)

Triggered when `anthropic.Anthropic()` resolves a credential (`ANTHROPIC_API_KEY` from
`.env` or the shell, `ANTHROPIC_AUTH_TOKEN`, or a local `ant auth login` profile)
**and** the call completes successfully.

```
diagnose()
  └─ _llm_diagnosis()
       1. import anthropic
       2. client = anthropic.Anthropic(          # credential from .env or env
              timeout=30.0, max_retries=1)
       3. _build_context(instance, alerts)        # flatten ORM rows to text
       4. client.messages.create(
              model="claude-opus-4-8", max_tokens=16000,
              thinking={"type": "adaptive"},
              system=<persona + 3-section contract>,
              messages=[{"role": "user", "content": task + context}])
       5. join blocks where block.type == "text", strip
       6. return text  (or None if empty)
  └─ return (text, "llm")
```

Characteristics: network round trip (typically a few seconds, at most 60 — see § 4.5),
token cost per call, output wording varies between calls, and reasoning quality is
highest — the model can weigh CPU history, alert timing, and instance age against each
other.

#### Path B — no API key, or the call fails (`source: "rule-based"`)

Triggered when **any** of the following occurs — all are caught by the same
`except Exception` and treated identically:

| Trigger | What actually raises |
|---|---|
| No credential configured at all | SDK raises on client construction / first request |
| Invalid or revoked key | `AuthenticationError` (401) |
| Key lacks model access | `PermissionDeniedError` (403) |
| Rate limit or quota exhausted | `RateLimitError` (429) |
| Provider outage | `APIStatusError` (5xx) |
| Provider slower than 30 s, twice | `APITimeoutError` after the retry (§ 4.5) |
| No network (offline demo, air-gapped CI) | `APIConnectionError` |
| `anthropic` package not installed | `ImportError` |
| Model returned only non-text blocks | text empty after strip → `None` |

```
diagnose()
  └─ _llm_diagnosis() ─── raises / returns None
       └─ logger.warning("LLM diagnosis unavailable, using rule-based fallback: %s", exc)
       └─ return None
  └─ _rule_based_diagnosis()
       1. unresolved = [a for a in alerts if not a.isResolved]
       2. build causes:
            cpuUsage >= CPU_WARNING_THRESHOLD  → resource-exhaustion cause
            any alert of type CPU_HIGH         → sustained-overload cause
            always                             → application fault, regional issue
       3. build numbered actions, interpolating updatedAt, instanceType,
          and len(unresolved)
       4. build prevention bullets referencing the 80% threshold
  └─ return (text, "rule-based")
```

Characteristics: no network call, zero cost, sub-millisecond, and **deterministic** —
the same instance state always produces the same text. It follows the same three
section headings as Path A, so the client renders it with the same component.

#### Side-by-side

| | Path A — with key | Path B — without key |
|---|---|---|
| `source` in response | `"llm"` | `"rule-based"` |
| HTTP status | `200` | `200` |
| Response schema | `DiagnosisResponse` | `DiagnosisResponse` (identical) |
| Section structure | Probable Causes / Recommended Actions / Prevention | same |
| External call | Yes — Anthropic Messages API | None |
| Latency | Seconds (network + inference), 60 s ceiling | Effectively instant |
| Cost | Per-token | Zero |
| Determinism | Varies per call | Fully deterministic |
| Reasoning depth | Correlates metrics, timing, and history | Fixed threshold rules only |
| Log output | — | `WARNING` with the underlying exception |
| Auth / RBAC | Enforced identically | Enforced identically |

The practical consequence: the API contract never changes, so the frontend and any
integration tests are written once. Enabling or disabling the key only changes the
quality of `diagnosis` and the value of `source` — never the shape of the response or
the status code. That is what makes the endpoint safe to demo on a machine with no
credentials.

---

## 3. Prompt Design

### 3.1 Roles

| Layer | Content | Rationale |
|---|---|---|
| `system` | Persona + output contract + length limit | Stable across all requests → cacheable, and keeps formatting rules out of user-controlled text |
| `user` | Task sentence + rendered instance context | The only part that varies per request |

### 3.2 System prompt

```text
You are a senior cloud infrastructure engineer at TechValley, an IT consulting firm
monitoring cloud instances for client companies. Given an instance in ERROR state,
produce a concise incident diagnosis in English with exactly three sections:
'Probable Causes' (2-4 bullet points, most likely first),
'Recommended Actions' (numbered, ordered steps), and
'Prevention' (1-2 bullets). Keep it under 250 words.
```

Each clause is deliberate:

| Clause | Why |
|---|---|
| *"senior cloud infrastructure engineer at TechValley… for client companies"* | Sets domain and audience. Output aims at an ops engineer, not an end user, so it may use terms like OOM kill, boot diagnostics, horizontal capacity. |
| *"Given an instance in ERROR state"* | Frames the task as incident triage rather than general commentary. |
| *"exactly three sections" + named headings* | Makes the output machine-checkable and renderable by the UI without parsing prose. |
| *"2-4 bullet points, most likely first"* | Forces prioritisation — the first bullet is the actionable hypothesis. |
| *"numbered, ordered steps"* | Actions are a runbook; order matters (inspect before restarting, restart before resizing). |
| *"in English"* | The system is used by a mixed-language team; pinning the language keeps output consistent. |
| *"under 250 words"* | Caps output tokens for cost/latency, and matches what fits in an incident card. |

The system prompt intentionally contains **no data** — only instructions. All volatile
content sits in the user turn, which is the correct ordering for prompt caching
(`tools → system → messages`): the stable prefix can be reused, and only the tail
changes per request.

### 3.3 User message

```text
Diagnose this cloud instance that is in ERROR state:

<context block>
```

The context block is produced by `_build_context()` as `key: value` lines — a compact,
unambiguous format that avoids JSON escaping noise:

```text
Instance name: web-prod-03
Region: ap-southeast-1
Type: MEDIUM
Status: ERROR
CPU usage: 94.2%
Monthly cost: $120.00
Launched at: 2026-05-11 09:30
Last status update: 2026-08-01 14:07
Recent alerts:
- [CPU_HIGH] 2026-08-01 13:52 (UNRESOLVED): CPU usage 94.2% exceeds 80% threshold
- [ERROR_DETECTED] 2026-08-01 14:07 (UNRESOLVED): Instance entered ERROR state
```

Field-selection rationale:

- `cpuUsage`, `instanceType` → capacity/right-sizing hypotheses.
- `region` → localises zone-level infrastructure incidents.
- `launchedAt` vs `updatedAt` → distinguishes "failed shortly after launch"
  (deployment/config problem) from "ran for weeks then died" (resource leak, drift).
- `monthlyCost` → lets the model frame resize advice against the cost review.
- Alert list with `alertType`, timestamp, and **resolved/UNRESOLVED** state → the
  strongest signal available. `UNRESOLVED` is upper-cased so the model reliably
  attends to open items.
- Alerts are capped at 10 and ordered newest-first, so the freshest evidence appears
  first even when truncated.
- When an instance has no alerts, the block renders the explicit line
  `- (no alerts on record)` rather than an empty section, which prevents the model
  from hallucinating alerts to fill the gap.

### 3.4 Request parameters

```python
client.messages.create(
    model="claude-opus-4-8",
    max_tokens=16000,
    thinking={"type": "adaptive"},
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": task + context}],
)
```

| Parameter | Value | Reason |
|---|---|---|
| `model` | `claude-opus-4-8` | Highest-capability tier for a reasoning-heavy diagnostic task; the write-up is read by an engineer who will act on it, so quality outweighs per-call cost at this volume. |
| `max_tokens` | `16000` | Adaptive thinking spends its reasoning tokens out of this **same** budget, so the cap has to cover the thinking as well as the ~250-word answer; a tight cap consumes it all and returns a truncated or empty result. The prompt's word limit, not this number, is what bounds the answer — a `stop_reason` of `max_tokens` is logged as a warning. |
| `thinking` | `{"type": "adaptive"}` | Correlating metrics with alert history is multi-step reasoning. Adaptive thinking lets the model choose its own depth per request instead of a fixed budget. On this model family adaptive is the only supported on-mode — a fixed `budget_tokens` budget is rejected — and omitting the parameter entirely would run with no thinking at all. |
| *(no `temperature` / `top_p`)* | — | Sampling parameters are not accepted on this model family and would return HTTP 400. Style is steered by the prompt instead. |
| *(no streaming)* | — | Output is a single short block delivered in one JSON response; there is no incremental UI to feed. |

### 3.5 Authentication

When `ANTHROPIC_API_KEY` is set, the key pydantic-settings read from `.env` is handed to
the client explicitly — the SDK reads the *environment variable*, never `.env`, so the
two are not the same thing. With nothing configured, the client is constructed without a
key and the SDK resolves credentials itself in the standard order: `ANTHROPIC_API_KEY`
from the shell, then `ANTHROPIC_AUTH_TOKEN`, then a local `ant auth login` profile. No
key is ever hard-coded, and the key is not required for the endpoint to work.

Both branches construct the client with the same request limits (§ 4.5).

---

## 4. Implementation

### 4.1 Call path

```python
def diagnose(instance, alerts) -> tuple[str, str]:
    """Returns (diagnosis_text, source) where source is 'llm' or 'rule-based'."""
    text = _llm_diagnosis(instance, alerts)
    if text is not None:
        return text, "llm"
    return _rule_based_diagnosis(instance, alerts), "rule-based"
```

`_llm_diagnosis()` returns `str | None`. `None` is the single, explicit signal for
"the LLM path did not produce usable text", covering every failure mode uniformly.

### 4.2 Response parsing

```python
text = "".join(block.text for block in response.content if block.type == "text").strip()
return text or None
```

`response.content` is a **list of typed blocks**, not a string. With adaptive thinking
enabled the list can contain `thinking` blocks alongside `text` blocks, so the code
filters on `block.type == "text"` rather than indexing `content[0]`. Blocks are joined
because a response may legitimately be split across several text blocks. An
empty-after-strip result is normalised to `None`, which routes to the fallback instead
of returning a blank diagnosis to the client.

### 4.3 Error handling and fallback

```python
except Exception as exc:      # no key, network error, rate limit, quota, etc.
    logger.warning("LLM diagnosis unavailable, using rule-based fallback: %s", exc)
    return None
```

A broad catch is intentional here: every failure mode has the same correct response
(fall back and keep serving), and the endpoint must not propagate a third-party outage
to the API consumer. The exception is logged at `WARNING` with its message, so
operators can still see *why* the LLM path was skipped.

The rule-based fallback mirrors the same three-section structure and derives its
content from the same inputs:

- CPU at or above `CPU_WARNING_THRESHOLD` (default 80%) → adds a resource-exhaustion cause.
- Any `CPU_HIGH` alert present → adds a sustained-overload cause.
- Two generic causes (application fault, regional infrastructure) are always included.
- Actions interpolate the real `updatedAt` timestamp, the real `instanceType`, and the
  count of unresolved alerts, so the fallback is still instance-specific rather than
  boilerplate.

Consumers can therefore render both paths with the same UI component, and the `source`
field makes the difference auditable.

### 4.4 Security and authorization

The endpoint sits behind the same guards as the rest of the API:

- `Depends(get_current_member)` — a valid HS256 JWT is required.
- `assert_client_access(member, instance.client)` — an `ADMIN` may diagnose any
  instance; a `CLIENT_MANAGER` only instances belonging to clients they manage.
- Only instance metadata and alert messages leave the process; member identities,
  client contact details, and credentials are never included in the prompt.

### 4.5 Request limits and the database connection

The provider call is the only part of this API that waits on a third party, and it is
the only handler that spends most of its time not touching the database. Two limits keep
that wait from becoming everyone else's problem
([../performance/PERFORMANCE_BUGS.md § PERF-03](../performance/PERFORMANCE_BUGS.md#perf-03)).

**A bounded wait.** The SDK's own defaults are a 600-second read timeout and 2 retries —
roughly 30 minutes for a single diagnosis. The service overrides both:

```python
TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 1
```

60 seconds worst case, and a diagnosis that exceeds it becomes an `APITimeoutError`,
which is caught like every other provider failure and answered from the rule-based
fallback. That is the right trade for this endpoint: an operator reading an incident card
is not served by an answer that arrives half an hour later, and the fallback — already
the answer on any machine without a key — is instant.

**No connection held across it.** `get_db` keeps a session, and therefore a pooled
connection, checked out for the whole request. The handler has everything it needs
loaded before the call, so it calls `db.close()` first:

```python
alerts = db.query(Alert)...all()
db.close()                                   # connection back to the pool
diagnosis, source = llm_service.diagnose(instance, alerts)
```

`Session.close()` *resets* the session rather than tearing it down, so `get_db` closing
it again after the response is a no-op. The rows it loaded are detached but **not**
expired — their loaded values stay readable, which is what lets `_build_context()` render
the prompt and the response body read `instance.instanceName` afterwards. The invariant
to preserve: **every field the prompt or the response needs must be loaded before
`db.close()`**, relationships included. Adding a field that lazy-loads after that line
raises `DetachedInstanceError`.

Measured with 20 concurrent diagnosis requests all inside the provider call at once: 20
connections held before, **0** after.

---

## 5. Output Format

### 5.1 HTTP response

`200 OK`, `application/json`, schema `DiagnosisResponse`:

| Field | Type | Description |
|---|---|---|
| `instanceId` | `int` | Instance primary key |
| `instanceName` | `string` | Human-readable instance name |
| `status` | `enum` | `RUNNING` \| `STOPPED` \| `ERROR` — status at diagnosis time |
| `diagnosis` | `string` | Multi-line diagnosis text (see 5.2) |
| `source` | `string` | `"llm"` when generated by Claude, `"rule-based"` when the fallback ran |

### 5.2 `diagnosis` text contract

Plain text (not Markdown-guaranteed), three sections in fixed order:

```text
Probable Causes
- <most likely cause>
- <next cause>
...

Recommended Actions
1. <first step>
2. <second step>
...

Prevention
- <preventive measure>
```

Constraints: 2–4 bullets under *Probable Causes*, ordered numbered steps under
*Recommended Actions*, 1–2 bullets under *Prevention*, ≤ 250 words total.

Because section headings are fixed by the system prompt, a client can split on them to
render each section separately. The `source` field should be surfaced in the UI (e.g.
an "AI-generated" vs "heuristic" badge) so operators know how much weight to give the
text.

### 5.3 Example

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/instances/5/diagnosis
```

```json
{
  "instanceId": 5,
  "instanceName": "web-prod-03",
  "status": "ERROR",
  "diagnosis": "Probable Causes\n- Resource exhaustion: CPU sustained at 94.2% immediately before failure, exceeding the capacity of a MEDIUM instance.\n- Repeated CPU_HIGH alerts over the preceding hour indicate the workload outgrew the instance rather than a one-off spike.\n- Application-level fault such as an OOM kill or an unhandled exception triggered by the load.\n\nRecommended Actions\n1. Pull system and application logs around 2026-08-01 14:07 to confirm the failure mode.\n2. Restart the instance and watch boot diagnostics for a clean start.\n3. If the logs confirm overload, resize from MEDIUM to LARGE or add a second instance behind the load balancer.\n4. Review deployments made in the last 24 hours and roll back if the timing correlates.\n5. Resolve the 2 open alerts once the instance is verified healthy.\n\nPrevention\n- Add an auto-restart health check and alert at 70% CPU so there is headroom before the 80% threshold fires.\n- Re-evaluate sizing against the workload trend during the monthly cost review.",
  "source": "llm"
}
```

The same request with **no** `ANTHROPIC_API_KEY` configured returns the same shape,
the same `200`, and the same three sections — only `diagnosis` and `source` differ:

```json
{
  "instanceId": 5,
  "instanceName": "web-prod-03",
  "status": "ERROR",
  "diagnosis": "Probable Causes\n- Resource exhaustion: CPU was at 94.2% before failure; the workload likely exceeded the instance capacity.\n- Repeated CPU_HIGH alerts suggest sustained overload leading to a crash.\n- Application-level fault (unhandled exception, OOM kill, or failed deployment).\n- Possible infrastructure/zone issue in region 'ap-southeast-1'.\n\nRecommended Actions\n1. Check system and application logs for the failure timestamp (last status change 2026-08-01 14:07).\n2. Attempt a controlled restart of the instance and monitor boot diagnostics.\n3. If overload-related, resize the instance (currently MEDIUM) or add horizontal capacity.\n4. Verify recent deployments/config changes and roll back if correlated.\n5. Resolve the 2 unresolved alert(s) after confirming recovery.\n\nPrevention\n- Configure auto-restart/health checks and capacity alerts below the 80% CPU threshold.\n- Review sizing against workload trends during the monthly cost review.",
  "source": "rule-based"
}
```

Server log for that call:

```
WARNING  app.services.llm_service  LLM diagnosis unavailable, using rule-based fallback: <exception message>
```

### 5.4 Error responses

| Status | Cause |
|---|---|
| `401` | Missing or invalid JWT |
| `403` | Member is not authorized for the instance's client |
| `404` | Instance does not exist |

There is **no** `502`/`503` for LLM failures — those are absorbed by the fallback and
surface only as `"source": "rule-based"`.

---

## 6. Configuration

```dotenv
# .env  (optional — the endpoint works without it)
ANTHROPIC_API_KEY=sk-ant-...
```

`ANTHROPIC_API_KEY` is declared in `Settings` ([app/config.py:14](../../app/config.py#L14))
with an empty default, so a missing key is a supported configuration rather than a
startup failure. `CPU_WARNING_THRESHOLD` (default `80.0`) is read by the rule-based
fallback so its causes stay consistent with the monitoring rules used elsewhere.

---

## 7. Verification

| Scenario | Setup | Expected |
|---|---|---|
| Happy path | Valid `ANTHROPIC_API_KEY` set, instance 5 in `ERROR` | `200`, `source: "llm"`, three sections present |
| No credentials | `ANTHROPIC_API_KEY` empty | `200`, `source: "rule-based"`, `WARNING` in logs |
| Invalid credentials | Wrong key | `200`, `source: "rule-based"` (auth error caught and logged) |
| Unauthorized | `CLIENT_MANAGER` token for another client's instance | `403` |
| Unknown instance | `id` not in DB | `404` |

---

## 8. Known Limitations and Future Work

- **Status is not enforced.** The prompt says "in ERROR state", but the endpoint accepts
  any instance regardless of status. A `RUNNING` instance will still be diagnosed as if
  it had failed. Either reject non-`ERROR` instances with `409`, or branch the prompt on
  status.
- **Unstructured output.** The three-section contract is enforced by instruction only.
  If the UI needs guaranteed fields, switch to structured outputs
  (`output_config.format` with a JSON schema) and return `causes[]`, `actions[]`,
  `prevention[]` as arrays instead of a text blob.
- **No caching.** Repeated calls for the same unchanged instance re-invoke the model.
  Caching the result keyed on `(instanceId, updatedAt, latest alert id)` would remove
  redundant calls.
- **Synchronous call.** The request blocks on the provider, occupying one of the 40
  threadpool workers for up to 60 seconds. Its database connection is released first
  (§ 4.5), so the pool is not affected, but the worker is still held; freeing that too
  means the async client (`AsyncAnthropic`) with an `async def` endpoint.
- **No usage tracking.** `response.usage` is discarded; recording input/output tokens
  per call would enable cost attribution per client.
- **Single language.** Output is pinned to English. A `lang` query parameter mapped
  into the system prompt would support the mixed-language team.

---

## 9. Related

| Document | Why |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Where `llm_service` sits in the layering |
| [ERD.md](ERD.md) | `instances` and `alerts` — the data fed into the prompt |
| [../api/ENDPOINTS.md](../api/ENDPOINTS.md) | `DiagnosisResponse` in the endpoint reference |
| [../api/ERRORS.md](../api/ERRORS.md) | Why there is no `5xx` for provider failures |
| [../business-rules/ALERTING.md](../business-rules/ALERTING.md) | How the alert history in the prompt is produced |
| [../performance/PERFORMANCE_BUGS.md](../performance/PERFORMANCE_BUGS.md) | PERF-03, the request limits and the connection release of § 4.5 |
| [../demo/WALKTHROUGH.md](../demo/WALKTHROUGH.md) | Demo step for this endpoint |
