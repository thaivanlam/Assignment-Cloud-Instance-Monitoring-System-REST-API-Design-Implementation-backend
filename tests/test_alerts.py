"""Functional tests for the alert history and resolution endpoints.

Rules under test: docs/business-rules/ALERTING.md and docs/business-rules/AUTHORIZATION.md.
"""

from datetime import timedelta

import pytest

from app.models import Alert
from app.models.models import utcnow


@pytest.fixture
def scanned(api, auth_headers):
    """Runs every monitoring scan as ADMIN so the full alert set exists.

    The seed records no alerts — they only exist once a scan has detected something.
    Four CPU_HIGH + two ERROR_DETECTED + three LONG_STOPPED = nine alerts.
    """
    client, db = api
    for path in ("/api/monitor/warnings", "/api/monitor/errors", "/api/monitor/long-stopped"):
        assert client.get(path, headers=auth_headers["admin"]).status_code == 200
    return client, db


def test_alert_history_is_empty_before_the_first_scan(api, auth_headers):
    client, _ = api

    response = client.get("/api/alerts", headers=auth_headers["admin"])

    assert response.status_code == 200
    assert response.json() == []


def test_alert_history_returns_every_detection_newest_first(scanned, auth_headers):
    client, _ = scanned

    response = client.get("/api/alerts", headers=auth_headers["admin"])

    assert response.status_code == 200
    alerts = response.json()
    assert len(alerts) == 9
    detected = [alert["detectedAt"] for alert in alerts]
    assert detected == sorted(detected, reverse=True)
    assert all(alert["isResolved"] is False for alert in alerts)
    assert all(alert["resolvedAt"] is None for alert in alerts)


def test_alert_history_carries_the_detection_message(scanned, auth_headers):
    client, _ = scanned

    errors = client.get("/api/alerts?alertType=ERROR_DETECTED", headers=auth_headers["admin"])
    warnings = client.get("/api/alerts?alertType=CPU_HIGH", headers=auth_headers["admin"])

    error_messages = {alert["instanceId"]: alert["message"] for alert in errors.json()}
    warning_messages = {alert["instanceId"]: alert["message"] for alert in warnings.json()}
    assert error_messages[5] == (
        "[CRITICAL] Instance 'hnlog-worker-01' (ap-southeast-1) is in ERROR state"
    )
    # The message records the reading that triggered the detection.
    assert "91.5%" in warning_messages[1]
    assert "96.3%" in warning_messages[14]


@pytest.mark.parametrize(
    "alert_type,expected_instances",
    [
        ("CPU_HIGH", {1, 4, 11, 14}),
        ("ERROR_DETECTED", {5, 9}),
        ("LONG_STOPPED", {3, 7, 13}),
    ],
)
def test_alert_history_filters_by_type(scanned, auth_headers, alert_type, expected_instances):
    client, _ = scanned

    response = client.get(f"/api/alerts?alertType={alert_type}", headers=auth_headers["admin"])

    assert response.status_code == 200
    assert {alert["instanceId"] for alert in response.json()} == expected_instances
    assert {alert["alertType"] for alert in response.json()} == {alert_type}


def test_alert_history_filters_by_resolved_state(scanned, auth_headers):
    client, db = scanned
    target = db.query(Alert).filter(Alert.instanceId == 5).one()

    client.patch(f"/api/alerts/{target.id}/resolve", headers=auth_headers["admin"])
    resolved = client.get("/api/alerts?isResolved=true", headers=auth_headers["admin"])
    unresolved = client.get("/api/alerts?isResolved=false", headers=auth_headers["admin"])

    assert [alert["id"] for alert in resolved.json()] == [target.id]
    assert len(unresolved.json()) == 8
    assert target.id not in [alert["id"] for alert in unresolved.json()]


def test_alert_history_filters_by_detection_date(scanned, auth_headers):
    client, _ = scanned
    today = utcnow().date()

    inclusive = client.get(
        f"/api/alerts?dateFrom={today}&dateTo={today}", headers=auth_headers["admin"]
    )
    from_tomorrow = client.get(
        f"/api/alerts?dateFrom={today + timedelta(days=1)}", headers=auth_headers["admin"]
    )
    until_yesterday = client.get(
        f"/api/alerts?dateTo={today - timedelta(days=1)}", headers=auth_headers["admin"]
    )

    # The bounds are inclusive on both ends and cover the whole day.
    assert len(inclusive.json()) == 9
    assert from_tomorrow.json() == []
    assert until_yesterday.json() == []


@pytest.mark.parametrize("query", ["alertType=BOGUS", "dateFrom=13-08-2026", "isResolved=maybe"])
def test_alert_history_validates_query_parameters(api, auth_headers, query):
    client, _ = api

    response = client.get(f"/api/alerts?{query}", headers=auth_headers["admin"])

    assert response.status_code == 422


def test_alert_history_is_scoped_to_the_callers_clients(scanned, auth_headers):
    client, _ = scanned

    manager1 = client.get("/api/alerts", headers=auth_headers["manager1"])
    manager2 = client.get("/api/alerts", headers=auth_headers["manager2"])

    assert {alert["instanceId"] for alert in manager1.json()} == {1, 3, 4, 5, 7, 9}
    assert {alert["instanceId"] for alert in manager2.json()} == {11, 13, 14}


def test_resolving_an_alert_stamps_it_once(scanned, auth_headers):
    client, db = scanned
    target = db.query(Alert).filter(Alert.instanceId == 1).one()

    first = client.patch(f"/api/alerts/{target.id}/resolve", headers=auth_headers["manager1"])
    second = client.patch(f"/api/alerts/{target.id}/resolve", headers=auth_headers["manager1"])

    assert first.status_code == 200
    assert first.json()["isResolved"] is True
    assert first.json()["resolvedAt"] is not None
    # Resolving again is accepted but must not move the timestamp.
    assert second.status_code == 200
    assert second.json()["resolvedAt"] == first.json()["resolvedAt"]


def test_resolving_removes_the_alert_from_the_report(scanned, auth_headers):
    client, db = scanned
    target = db.query(Alert).filter(Alert.instanceId == 9).one()

    before = client.get("/api/monitor/report", headers=auth_headers["admin"]).json()
    client.patch(f"/api/alerts/{target.id}/resolve", headers=auth_headers["admin"])
    after = client.get("/api/monitor/report", headers=auth_headers["admin"]).json()

    assert before["unresolvedAlertCount"] == 9
    assert after["unresolvedAlertCount"] == 8
    assert target.id not in [alert["id"] for alert in after["unresolvedAlerts"]]


def test_resolving_another_managers_alert_is_forbidden(scanned, auth_headers):
    client, db = scanned
    target = db.query(Alert).filter(Alert.instanceId == 1).one()

    response = client.patch(f"/api/alerts/{target.id}/resolve", headers=auth_headers["manager2"])

    assert response.status_code == 403
    db.refresh(target)
    assert target.isResolved is False


def test_resolving_an_unknown_alert_is_404(api, auth_headers):
    client, _ = api

    response = client.patch("/api/alerts/999/resolve", headers=auth_headers["admin"])

    assert response.status_code == 404
    # The alert controller raises HTTPException, so this body has no "error" key.
    assert response.json() == {"detail": "Alert 999 not found"}
