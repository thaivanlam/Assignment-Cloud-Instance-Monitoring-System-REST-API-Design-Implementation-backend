"""Functional tests for GET /api/instances/{id}/diagnosis.

The Anthropic call is replaced in every test — the suite must never reach the network,
and the endpoint's contract is that it answers either way. The diagnosis cache is covered
at the end of the file.
Rules under test: docs/design/LLM_FEATURE.md.
"""

import types

import anthropic
import pytest

from app.config import settings
from app.services import llm_service

REAL_LLM_DIAGNOSIS = llm_service._llm_diagnosis


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Default to 'no LLM available', the state of a machine without an API key."""
    monkeypatch.setattr(llm_service, "_llm_diagnosis", lambda instance, alerts: None)
    # The provider client is built once per process and cached (PERF-14). Clearing it per
    # test keeps a stubbed SDK from leaking a client into the next test that builds one.
    monkeypatch.setattr(llm_service, "_client", None)
    return monkeypatch


def test_diagnosis_falls_back_to_a_rule_based_answer(api, auth_headers):
    client, _ = api

    response = client.get("/api/instances/5/diagnosis", headers=auth_headers["manager1"])

    assert response.status_code == 200
    body = response.json()
    assert body["instanceId"] == 5
    assert body["instanceName"] == "hnlog-worker-01"
    assert body["status"] == "ERROR"
    assert body["source"] == "rule-based"
    # The fallback keeps the same three sections the prompt asks the model for.
    assert "Probable Causes" in body["diagnosis"]
    assert "Recommended Actions" in body["diagnosis"]
    assert "Prevention" in body["diagnosis"]
    assert "ap-southeast-1" in body["diagnosis"]


def test_diagnosis_uses_the_model_answer_when_one_is_available(api, auth_headers, offline):
    client, _ = api
    offline.setattr(llm_service, "_llm_diagnosis", lambda instance, alerts: "Model answer.")

    response = client.get("/api/instances/5/diagnosis", headers=auth_headers["manager1"])

    assert response.status_code == 200
    assert response.json()["source"] == "llm"
    assert response.json()["diagnosis"] == "Model answer."


def test_diagnosis_is_given_the_instance_and_its_recent_alerts(api, auth_headers, offline):
    client, _ = api
    captured = {}

    def record(instance, alerts):
        captured["instance"] = instance
        captured["alerts"] = alerts
        return None

    offline.setattr(llm_service, "_llm_diagnosis", record)

    # The error scan records an ERROR_DETECTED alert for instance 5 first.
    client.get("/api/monitor/errors", headers=auth_headers["manager1"])
    response = client.get("/api/instances/5/diagnosis", headers=auth_headers["manager1"])

    assert response.status_code == 200
    assert captured["instance"].id == 5
    assert [alert.alertType.value for alert in captured["alerts"]] == ["ERROR_DETECTED"]
    assert all(alert.instanceId == 5 for alert in captured["alerts"])


def test_diagnosis_survives_a_provider_failure(api, auth_headers, offline):
    """No 5xx ever leaves the API for an LLM outage — the real provider call runs here,
    against an SDK stubbed to fail."""
    client, _ = api

    def broken_sdk(*args, **kwargs):
        raise RuntimeError("provider is down")

    offline.setattr(llm_service, "_llm_diagnosis", REAL_LLM_DIAGNOSIS)
    offline.setattr(anthropic, "Anthropic", broken_sdk)

    response = client.get("/api/instances/5/diagnosis", headers=auth_headers["manager1"])

    assert response.status_code == 200
    assert response.json()["source"] == "rule-based"
    assert "Probable Causes" in response.json()["diagnosis"]


def test_diagnosis_returns_the_text_the_provider_produced(api, auth_headers, offline):
    """Exercises the real provider path with a stubbed SDK: prompt assembly, response
    parsing, and the 'llm' source marker."""
    client, _ = api
    sent = {}

    def fake_create(**kwargs):
        sent.update(kwargs)
        return types.SimpleNamespace(
            stop_reason="end_turn",
            content=[
                types.SimpleNamespace(type="thinking", thinking="..."),
                types.SimpleNamespace(type="text", text="Probable Causes\n- Disk full."),
            ],
        )

    offline.setattr(llm_service, "_llm_diagnosis", REAL_LLM_DIAGNOSIS)
    offline.setattr(
        anthropic,
        "Anthropic",
        lambda *args, **kwargs: types.SimpleNamespace(
            messages=types.SimpleNamespace(create=fake_create)
        ),
    )

    response = client.get("/api/instances/5/diagnosis", headers=auth_headers["manager1"])

    assert response.status_code == 200
    assert response.json()["source"] == "llm"
    # Only text blocks reach the caller; thinking blocks are dropped.
    assert response.json()["diagnosis"] == "Probable Causes\n- Disk full."
    # The prompt describes the instance under diagnosis.
    prompt = sent["messages"][0]["content"]
    assert "hnlog-worker-01" in prompt
    assert "Status: ERROR" in prompt


def test_the_provider_client_is_built_once_and_reused(api, auth_headers, offline):
    """PERF-14: one SDK client serves the process, so a second diagnosis reuses its
    connection pool instead of opening a new one."""
    client, _ = api
    built = []

    def fake_create(**kwargs):
        return types.SimpleNamespace(
            stop_reason="end_turn",
            content=[types.SimpleNamespace(type="text", text="Diagnosis from the model.")],
        )

    def fake_anthropic(*args, **kwargs):
        # Only the limits are recorded — an api_key would otherwise reach a failure report.
        built.append({key: kwargs.get(key) for key in ("timeout", "max_retries")})
        return types.SimpleNamespace(messages=types.SimpleNamespace(create=fake_create))

    offline.setattr(llm_service, "_llm_diagnosis", REAL_LLM_DIAGNOSIS)
    offline.setattr(anthropic, "Anthropic", fake_anthropic)

    first = client.get("/api/instances/5/diagnosis", headers=auth_headers["manager1"])
    second = client.get("/api/instances/1/diagnosis", headers=auth_headers["manager1"])

    assert [first.status_code, second.status_code] == [200, 200]
    assert [first.json()["source"], second.json()["source"]] == ["llm", "llm"]
    # Two diagnoses, one client — the assertion the finding is about.
    assert len(built) == 1
    # The PERF-03 request limits ride on the shared client, not on a per-call one.
    assert built[0]["timeout"] == llm_service.TIMEOUT_SECONDS
    assert built[0]["max_retries"] == llm_service.MAX_RETRIES


def test_diagnosis_works_for_a_healthy_instance_too(api, auth_headers):
    client, _ = api

    response = client.get("/api/instances/1/diagnosis", headers=auth_headers["manager1"])

    assert response.status_code == 200
    assert response.json()["status"] == "RUNNING"
    # Instance 1 sits at 91.5% CPU, so the resource-exhaustion cause is included.
    assert "91.5%" in response.json()["diagnosis"]


def test_diagnosis_enforces_scope_and_existence(api, auth_headers):
    client, _ = api

    forbidden = client.get("/api/instances/10/diagnosis", headers=auth_headers["manager1"])
    missing = client.get("/api/instances/999/diagnosis", headers=auth_headers["admin"])

    assert forbidden.status_code == 403
    assert missing.status_code == 404
    assert missing.json()["error"] == "NotFound"


# ---------- the diagnosis cache ----------


@pytest.fixture
def model_calls(offline):
    """A stand-in model that answers every call differently and records each one."""
    calls = []

    def answer(instance, alerts):
        calls.append(instance.id)
        return f"Model answer #{len(calls)} for instance {instance.id}."

    offline.setattr(llm_service, "_llm_diagnosis", answer)
    return calls


def _diagnose(client, headers, instance_id=5):
    response = client.get(f"/api/instances/{instance_id}/diagnosis", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_an_unchanged_instance_reuses_the_model_answer(api, auth_headers, model_calls):
    client, _ = api

    first = _diagnose(client, auth_headers["manager1"])
    second = _diagnose(client, auth_headers["admin"])

    assert model_calls == [5]
    assert second["diagnosis"] == first["diagnosis"] == "Model answer #1 for instance 5."
    assert second["source"] == "llm"


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(
            lambda client, headers: client.get("/api/monitor/errors", headers=headers),
            id="a-new-alert",
        ),
        pytest.param(
            lambda client, headers: client.patch(
                "/api/instances/5/status",
                json={"status": "RUNNING", "cpuUsage": 12.0},
                headers=headers,
            ),
            id="a-status-change",
        ),
    ],
)
def test_a_changed_instance_is_diagnosed_again(api, auth_headers, model_calls, change):
    client, _ = api
    headers = auth_headers["admin"]

    first = _diagnose(client, headers)
    assert change(client, headers).status_code == 200
    second = _diagnose(client, headers)

    assert model_calls == [5, 5]
    assert second["diagnosis"] != first["diagnosis"]


def test_a_cached_answer_expires(api, auth_headers, model_calls, clock):
    client, _ = api

    _diagnose(client, auth_headers["admin"])
    clock.advance(settings.DIAGNOSIS_CACHE_TTL_SECONDS)
    _diagnose(client, auth_headers["admin"])

    assert model_calls == [5, 5]


def test_the_rule_based_fallback_is_never_cached(api, auth_headers, offline):
    """A machine that gains a key must start answering from the model at once."""
    client, _ = api
    offline.setattr(llm_service, "_llm_diagnosis", lambda instance, alerts: None)
    assert _diagnose(client, auth_headers["admin"])["source"] == "rule-based"

    offline.setattr(llm_service, "_llm_diagnosis", lambda instance, alerts: "Now from the model.")

    assert _diagnose(client, auth_headers["admin"])["source"] == "llm"


def test_a_zero_ttl_disables_the_cache(api, auth_headers, model_calls, monkeypatch, store):
    client, _ = api
    monkeypatch.setattr(settings, "DIAGNOSIS_CACHE_TTL_SECONDS", 0)

    _diagnose(client, auth_headers["admin"])
    _diagnose(client, auth_headers["admin"])

    assert model_calls == [5, 5]
    assert not any(key.startswith("diagnosis:") for key in store._data)


def test_the_cache_works_through_redis(api, auth_headers, model_calls, redis_server):
    client, _ = api

    _diagnose(client, auth_headers["admin"])
    cached = _diagnose(client, auth_headers["admin"])

    assert model_calls == [5]
    assert cached["diagnosis"] == "Model answer #1 for instance 5."
    [key] = redis_server.client.keys(f"{settings.REDIS_KEY_PREFIX}diagnosis:5:*")
    assert 0 < redis_server.client.ttl(key) <= settings.DIAGNOSIS_CACHE_TTL_SECONDS


def test_diagnosis_still_answers_when_redis_is_down(api, auth_headers, model_calls, redis_server):
    client, _ = api
    redis_server.server.connected = False

    first = _diagnose(client, auth_headers["admin"])
    second = _diagnose(client, auth_headers["admin"])

    # No cache to read or write, so every call goes to the model — but every call answers.
    assert model_calls == [5, 5]
    assert [first["source"], second["source"]] == ["llm", "llm"]
