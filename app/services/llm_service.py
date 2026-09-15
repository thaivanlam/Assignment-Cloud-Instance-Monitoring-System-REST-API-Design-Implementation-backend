"""LLM-powered diagnosis for ERROR instances (GET /api/instances/{id}/diagnosis).

Uses the official Anthropic SDK when credentials are available
(ANTHROPIC_API_KEY env var / .env, or an `ant auth login` profile).
Falls back to a deterministic rule-based diagnosis otherwise, so the endpoint
always works in demo environments without an API key.
"""

import hashlib
import logging
import threading

from app.config import settings
from app.core.store import get_store
from app.models import Alert, Instance

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = (
    "You are a senior cloud infrastructure engineer at TechValley, an IT "
    "consulting firm monitoring cloud instances for client companies. "
    "Given an instance in ERROR state, produce a concise incident diagnosis "
    "in English with exactly three sections: "
    "'Probable Causes' (2-4 bullet points, most likely first), "
    "'Recommended Actions' (numbered, ordered steps), and "
    "'Prevention' (1-2 bullets). Keep it under 250 words."
)

# The SDK's own defaults are a 600-second read timeout and 2 retries — up to ~30 minutes
# of waiting for a single diagnosis, during which the request holds a threadpool worker.
# An operator reading an incident card is not served by an answer that late: past 30
# seconds the deterministic fallback is the better response, and one retry still absorbs
# a transient connection error. See docs/performance/PERFORMANCE_BUGS.md § PERF-03.
TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 1

# One client for the process. Each anthropic.Anthropic() owns an httpx client with its own
# connection pool, so building one per request meant a TCP and TLS handshake per diagnosis
# and a pool nobody ever closed. See docs/performance/PERFORMANCE_BUGS.md § PERF-14.
_client = None
_client_lock = threading.Lock()


def _get_client():
    """The shared Anthropic client, built on first use.

    The SDK reads the ANTHROPIC_API_KEY *environment variable* — it never reads .env, so
    the key pydantic-settings loaded has to be handed over explicitly. With nothing
    configured, fall through to the SDK's own credential resolution (env var,
    ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile).

    A construction failure is not cached: with no credential at all the SDK raises here and
    the next call is free to try again, so a keyless process keeps behaving exactly as it
    did rather than latching into the fallback. (`settings` is read at import, so this is
    not a way to reload a key from .env without a restart.) The double-checked lock means
    the client is built exactly once even if several diagnosis requests reach a cold
    process together.
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                import anthropic

                api_key = settings.ANTHROPIC_API_KEY.strip()
                limits = {"timeout": TIMEOUT_SECONDS, "max_retries": MAX_RETRIES}
                _client = (
                    anthropic.Anthropic(api_key=api_key, **limits) if api_key
                    else anthropic.Anthropic(**limits)
                )
    return _client


def _build_context(instance: Instance, alerts: list[Alert]) -> str:
    alert_lines = "\n".join(
        f"- [{a.alertType.value}] {a.detectedAt:%Y-%m-%d %H:%M} "
        f"({'resolved' if a.isResolved else 'UNRESOLVED'}): {a.message}"
        for a in alerts
    ) or "- (no alerts on record)"

    return (
        f"Instance name: {instance.instanceName}\n"
        f"Region: {instance.region}\n"
        f"Type: {instance.instanceType.value}\n"
        f"Status: {instance.status.value}\n"
        f"CPU usage: {instance.cpuUsage:.1f}%\n"
        f"Monthly cost: ${instance.monthlyCost:.2f}\n"
        f"Launched at: {instance.launchedAt:%Y-%m-%d %H:%M}\n"
        f"Last status update: {instance.updatedAt:%Y-%m-%d %H:%M}\n"
        f"Recent alerts:\n{alert_lines}"
    )


def _user_message(instance: Instance, alerts: list[Alert]) -> str:
    return "Diagnose this cloud instance that is in ERROR state:\n\n" + _build_context(
        instance, alerts
    )


def _cache_key(instance: Instance, alerts: list[Alert]) -> str:
    """A key that changes whenever the model would be asked something different.

    It hashes the request itself — model, system prompt and the rendered user message —
    rather than a hand-picked list of fields. A status change, a new or resolved alert, a
    CPU update or a prompt edit therefore lands on a new key on its own, and nothing ever
    has to invalidate an old one: it simply stops being asked for and expires.
    """
    request = "\x00".join((MODEL, SYSTEM_PROMPT, _user_message(instance, alerts)))
    return f"diagnosis:{instance.id}:{hashlib.sha256(request.encode()).hexdigest()}"


def _llm_diagnosis(instance: Instance, alerts: list[Alert]) -> str | None:
    try:
        response = _get_client().messages.create(
            model=MODEL,
            # Adaptive thinking spends thinking tokens out of this same budget, so a
            # tight cap can consume it all and return an empty or truncated answer.
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _user_message(instance, alerts)}],
        )
        if response.stop_reason == "max_tokens":
            logger.warning("LLM diagnosis hit the max_tokens cap; the answer may be truncated")
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        return text or None
    except Exception as exc:  # no key, network error, etc. -> fall back
        logger.warning("LLM diagnosis unavailable, using rule-based fallback: %s", exc)
        return None


def _rule_based_diagnosis(instance: Instance, alerts: list[Alert]) -> str:
    unresolved = [a for a in alerts if not a.isResolved]
    causes = []
    if instance.cpuUsage >= settings.CPU_WARNING_THRESHOLD:
        causes.append(
            f"- Resource exhaustion: CPU was at {instance.cpuUsage:.1f}% before failure; "
            "the workload likely exceeded the instance capacity."
        )
    if any(a.alertType.value == "CPU_HIGH" for a in alerts):
        causes.append("- Repeated CPU_HIGH alerts suggest sustained overload leading to a crash.")
    causes.append("- Application-level fault (unhandled exception, OOM kill, or failed deployment).")
    causes.append(f"- Possible infrastructure/zone issue in region '{instance.region}'.")

    return (
        "Probable Causes\n"
        + "\n".join(causes)
        + "\n\nRecommended Actions\n"
        "1. Check system and application logs for the failure timestamp "
        f"(last status change {instance.updatedAt:%Y-%m-%d %H:%M}).\n"
        "2. Attempt a controlled restart of the instance and monitor boot diagnostics.\n"
        "3. If overload-related, resize the instance "
        f"(currently {instance.instanceType.value}) or add horizontal capacity.\n"
        "4. Verify recent deployments/config changes and roll back if correlated.\n"
        f"5. Resolve the {len(unresolved)} unresolved alert(s) after confirming recovery.\n\n"
        "Prevention\n"
        "- Configure auto-restart/health checks and capacity alerts below the 80% CPU threshold.\n"
        "- Review sizing against workload trends during the monthly cost review."
    )


def diagnose(instance: Instance, alerts: list[Alert]) -> tuple[str, str]:
    """Returns (diagnosis_text, source) where source is 'llm' or 'rule-based'.

    A model answer is reused for `DIAGNOSIS_CACHE_TTL_SECONDS` while the instance and its
    alerts are unchanged (`_cache_key`), so reopening an incident card does not pay for a
    second provider call. Only model answers are stored: the rule-based text is instant to
    rebuild, and caching it would keep serving the fallback after a key is configured.
    """
    ttl = settings.DIAGNOSIS_CACHE_TTL_SECONDS
    key = _cache_key(instance, alerts) if ttl > 0 else None
    if key is not None and (cached := get_store().get(key)) is not None:
        return cached, "llm"

    text = _llm_diagnosis(instance, alerts)
    if text is not None:
        if key is not None:
            get_store().set(key, text, ttl=ttl)
        return text, "llm"
    return _rule_based_diagnosis(instance, alerts), "rule-based"
