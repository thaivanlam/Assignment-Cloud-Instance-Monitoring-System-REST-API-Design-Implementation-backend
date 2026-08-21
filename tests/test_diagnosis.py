"""Functional tests for GET /api/instances/{id}/diagnosis.

The Anthropic call is replaced in every test — the suite must never reach the network,
and the endpoint's contract is that it answers either way.
Rules under test: docs/design/LLM_FEATURE.md.
"""

import types

import anthropic
import pytest

from app.services import llm_service

REAL_LLM_DIAGNOSIS = llm_service._llm_diagnosis


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Default to 'no LLM available', the state of a machine without an API key."""
    monkeypatch.setattr(llm_service, "_llm_diagnosis", lambda instance, alerts: None)
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
