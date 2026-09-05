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
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "size": 10,
        "totalPages": 0,
    }


def test_alert_history_returns_every_detection_newest_first(scanned, auth_headers):
    client, _ = scanned

    response = client.get("/api/alerts", headers=auth_headers["admin"])

    assert response.status_code == 200
    body = response.json()
    alerts = body["items"]
    # Nine alerts fit inside the default page, so the page carries all of them.
    assert body["total"] == 9
    assert body["totalPages"] == 1
    assert len(alerts) == 9
    detected = [alert["detectedAt"] for alert in alerts]
    assert detected == sorted(detected, reverse=True)
    assert all(alert["isResolved"] is False for alert in alerts)
    assert all(alert["resolvedAt"] is None for alert in alerts)


def test_alert_history_carries_the_detection_message(scanned, auth_headers):
    client, _ = scanned

    errors = client.get("/api/alerts?alertType=ERROR_DETECTED", headers=auth_headers["admin"])
    warnings = client.get("/api/alerts?alertType=CPU_HIGH", headers=auth_headers["admin"])

    error_messages = {a["instanceId"]: a["message"] for a in errors.json()["items"]}
    warning_messages = {a["instanceId"]: a["message"] for a in warnings.json()["items"]}
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
    alerts = response.json()["items"]
    assert {alert["instanceId"] for alert in alerts} == expected_instances
    assert {alert["alertType"] for alert in alerts} == {alert_type}
    assert response.json()["total"] == len(expected_instances)


def test_alert_history_filters_by_resolved_state(scanned, auth_headers):
    client, db = scanned
    target = db.query(Alert).filter(Alert.instanceId == 5).one()

    client.patch(f"/api/alerts/{target.id}/resolve", headers=auth_headers["admin"])
    resolved = client.get("/api/alerts?isResolved=true", headers=auth_headers["admin"])
    unresolved = client.get("/api/alerts?isResolved=false", headers=auth_headers["admin"])

    assert [alert["id"] for alert in resolved.json()["items"]] == [target.id]
    assert unresolved.json()["total"] == 8
    assert target.id not in [alert["id"] for alert in unresolved.json()["items"]]


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
    assert inclusive.json()["total"] == 9
    assert from_tomorrow.json()["items"] == []
    assert until_yesterday.json()["items"] == []


@pytest.mark.parametrize("query", ["alertType=BOGUS", "dateFrom=13-08-2026", "isResolved=maybe"])
def test_alert_history_validates_query_parameters(api, auth_headers, query):
    client, _ = api

    response = client.get(f"/api/alerts?{query}", headers=auth_headers["admin"])

    assert response.status_code == 422


def test_alert_history_is_scoped_to_the_callers_clients(scanned, auth_headers):
    client, _ = scanned

    manager1 = client.get("/api/alerts", headers=auth_headers["manager1"])
    manager2 = client.get("/api/alerts", headers=auth_headers["manager2"])

    assert {alert["instanceId"] for alert in manager1.json()["items"]} == {1, 3, 4, 5, 7, 9}
    assert {alert["instanceId"] for alert in manager2.json()["items"]} == {11, 13, 14}


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


def test_a_manager_with_no_clients_resolves_nothing(scanned, empty_scope_headers):
    """The alert guard reaches a client through two hops, and an empty scope must stop it.

    `resolve_alert` gets the alert's `clientId` off the instance the alert query already
    loaded and checks it against the caller's scope, where it used to walk
    `alert.instance.client` (docs/performance/PERFORMANCE_BUGS.md § PERF-11). A manager
    with no clients owns no instance either, so every alert in the table is out of reach.
    """
    client, db = scanned
    target = db.query(Alert).filter(Alert.instanceId == 1).one()

    response = client.patch(f"/api/alerts/{target.id}/resolve", headers=empty_scope_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "CLIENT_MANAGER can only access clients assigned to them"
    )
    db.refresh(target)
    assert target.isResolved is False


def test_resolving_an_unknown_alert_is_404(api, auth_headers):
    client, _ = api

    response = client.patch("/api/alerts/999/resolve", headers=auth_headers["admin"])

    assert response.status_code == 404
    # The alert controller raises HTTPException, so this body has no "error" key.
    assert response.json() == {"detail": "Alert 999 not found"}


# ------------------------------------------------------------------------ pagination


def test_alert_history_is_paginated(scanned, auth_headers):
    client, _ = scanned

    first = client.get("/api/alerts?page=1&size=4", headers=auth_headers["admin"])
    second = client.get("/api/alerts?page=2&size=4", headers=auth_headers["admin"])
    third = client.get("/api/alerts?page=3&size=4", headers=auth_headers["admin"])

    assert first.json()["total"] == 9
    assert first.json()["totalPages"] == 3
    assert first.json()["size"] == 4
    assert [len(page.json()["items"]) for page in (first, second, third)] == [4, 4, 1]
    # `total` counts the whole filtered set, not the page.
    assert all(page.json()["total"] == 9 for page in (first, second, third))


def test_alert_pages_partition_the_history_without_gaps_or_repeats(scanned, auth_headers):
    client, _ = scanned

    walked = []
    for page in (1, 2, 3, 4):
        response = client.get(f"/api/alerts?page={page}&size=4", headers=auth_headers["admin"])
        walked.extend(alert["id"] for alert in response.json()["items"])

    # Every alert of a scan carries the same detectedAt, so this only holds because the
    # ordering breaks that tie on a unique key.
    everything = client.get("/api/alerts?size=100", headers=auth_headers["admin"])
    assert walked == [alert["id"] for alert in everything.json()["items"]]
    assert len(walked) == len(set(walked)) == 9


def test_alert_history_page_past_the_end_is_empty_not_404(scanned, auth_headers):
    client, _ = scanned

    response = client.get("/api/alerts?page=99", headers=auth_headers["admin"])

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 9


@pytest.mark.parametrize("query", ["page=0", "size=0", "size=101"])
def test_alert_history_rejects_out_of_range_paging(scanned, auth_headers, query):
    client, _ = scanned

    response = client.get(f"/api/alerts?{query}", headers=auth_headers["admin"])

    assert response.status_code == 422


def test_alert_pagination_applies_after_filtering_and_scoping(scanned, auth_headers):
    client, _ = scanned

    response = client.get(
        "/api/alerts?alertType=CPU_HIGH&size=2", headers=auth_headers["manager1"]
    )

    # manager1 sees two of the four CPU_HIGH alerts; `total` is that scoped count.
    assert response.json()["total"] == 2
    assert {alert["instanceId"] for alert in response.json()["items"]} == {1, 4}


def test_deleting_an_instance_removes_its_alerts_from_the_history(scanned, auth_headers):
    """No alert outlives its instance, so the history never holds an orphan.

    `list_alerts` joins `instances` only when a CLIENT_MANAGER's scope has to be
    applied (docs/performance/PERFORMANCE_BUGS.md § PERF-09). An ADMIN's query has no
    join, so a row whose `instanceId` pointed at nothing would now be listed where the
    inner join used to hide it. It cannot: `Instance.alerts` cascades the delete. This
    pins that, because losing the cascade would turn a storage bug into a visible one.
    """
    client, db = scanned
    # Instance 3 is STOPPED, so it is deletable, and its LONG_STOPPED alert exists.
    assert db.query(Alert).filter(Alert.instanceId == 3).count() == 1

    assert client.delete("/api/instances/3", headers=auth_headers["manager1"]).status_code == 204

    history = client.get("/api/alerts?size=100", headers=auth_headers["admin"]).json()
    assert history["total"] == 8
    assert 3 not in {alert["instanceId"] for alert in history["items"]}
    assert db.query(Alert).filter(Alert.instanceId == 3).count() == 0
