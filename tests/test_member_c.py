from app.models import Alert, AlertType, Instance


def _alert_count(db, alert_type: AlertType) -> int:
    return (
        db.query(Alert)
        .filter(Alert.alertType == alert_type, Alert.isResolved.is_(False))
        .count()
    )


def test_member_c_endpoints_require_authentication(api):
    client, _ = api

    for method, path, body in [
        ("get", "/api/monitor/warnings", None),
        ("get", "/api/monitor/errors", None),
        ("get", "/api/monitor/long-stopped", None),
        ("get", "/api/monitor/report", None),
        ("patch", "/api/instances/1/status", {"status": "STOPPED"}),
    ]:
        response = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)
        assert response.status_code == 401


def test_status_change_is_scoped_and_idempotent(api, auth_headers):
    client, db = api
    instance = db.get(Instance, 3)
    original_updated_at = instance.updatedAt

    # Repeating the current state must not reset the 48-hour STOPPED clock.
    no_op = client.patch(
        "/api/instances/3/status",
        headers=auth_headers["manager1"],
        json={"status": "STOPPED"},
    )
    assert no_op.status_code == 200
    db.refresh(instance)
    assert instance.updatedAt == original_updated_at

    changed = client.patch(
        "/api/instances/5/status",
        headers=auth_headers["manager1"],
        json={"status": "RUNNING", "cpuUsage": 23.4},
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "RUNNING"
    assert changed.json()["cpuUsage"] == 23.4

    stopped = client.patch(
        "/api/instances/5/status",
        headers=auth_headers["manager1"],
        json={"status": "STOPPED"},
    )
    assert stopped.status_code == 200
    assert stopped.json()["cpuUsage"] == 0.0

    forbidden = client.patch(
        "/api/instances/10/status",
        headers=auth_headers["manager1"],
        json={"status": "STOPPED"},
    )
    assert forbidden.status_code == 403


def test_warnings_are_scoped_auto_recorded_and_deduplicated(api, auth_headers):
    client, db = api

    manager1 = client.get("/api/monitor/warnings", headers=auth_headers["manager1"])
    assert manager1.status_code == 200
    assert [item["id"] for item in manager1.json()] == [1, 4]
    assert _alert_count(db, AlertType.CPU_HIGH) == 2

    repeated = client.get("/api/monitor/warnings", headers=auth_headers["manager1"])
    assert repeated.status_code == 200
    assert _alert_count(db, AlertType.CPU_HIGH) == 2

    manager2 = client.get("/api/monitor/warnings", headers=auth_headers["manager2"])
    assert manager2.status_code == 200
    assert [item["id"] for item in manager2.json()] == [11, 14]
    assert _alert_count(db, AlertType.CPU_HIGH) == 4

    first_alert = (
        db.query(Alert)
        .filter(Alert.instanceId == 1, Alert.alertType == AlertType.CPU_HIGH)
        .one()
    )
    resolved = client.patch(
        f"/api/alerts/{first_alert.id}/resolve",
        headers=auth_headers["manager1"],
    )
    assert resolved.status_code == 200

    client.get("/api/monitor/warnings", headers=auth_headers["manager1"])
    assert db.query(Alert).filter(
        Alert.instanceId == 1,
        Alert.alertType == AlertType.CPU_HIGH,
    ).count() == 2
    assert _alert_count(db, AlertType.CPU_HIGH) == 4


def test_error_and_long_stopped_monitoring_auto_record_without_duplicates(api, auth_headers):
    client, db = api

    errors = client.get("/api/monitor/errors", headers=auth_headers["admin"])
    long_stopped = client.get("/api/monitor/long-stopped", headers=auth_headers["admin"])

    assert errors.status_code == 200
    assert [item["id"] for item in errors.json()] == [5, 9]
    assert long_stopped.status_code == 200
    assert [item["id"] for item in long_stopped.json()] == [3, 7, 13]
    assert _alert_count(db, AlertType.ERROR_DETECTED) == 2
    assert _alert_count(db, AlertType.LONG_STOPPED) == 3

    client.get("/api/monitor/errors", headers=auth_headers["admin"])
    client.get("/api/monitor/long-stopped", headers=auth_headers["admin"])
    assert _alert_count(db, AlertType.ERROR_DETECTED) == 2
    assert _alert_count(db, AlertType.LONG_STOPPED) == 3


def test_full_report_and_manager_scope(api, auth_headers):
    client, _ = api

    client.get("/api/monitor/warnings", headers=auth_headers["admin"])
    client.get("/api/monitor/errors", headers=auth_headers["admin"])
    client.get("/api/monitor/long-stopped", headers=auth_headers["admin"])

    admin_report = client.get("/api/monitor/report", headers=auth_headers["admin"])
    assert admin_report.status_code == 200
    assert admin_report.json()["instanceCountByStatus"] == {
        "RUNNING": 10,
        "STOPPED": 3,
        "ERROR": 2,
    }
    assert admin_report.json()["warningCount"] == 4
    assert admin_report.json()["totalMonthlyCost"] == 2100.0
    assert admin_report.json()["unresolvedAlertCount"] == 9

    manager_report = client.get("/api/monitor/report", headers=auth_headers["manager1"])
    assert manager_report.status_code == 200
    assert manager_report.json()["instanceCountByStatus"] == {
        "RUNNING": 5,
        "STOPPED": 2,
        "ERROR": 2,
    }
    assert manager_report.json()["warningCount"] == 2
    assert manager_report.json()["totalMonthlyCost"] == 1260.0
    assert manager_report.json()["unresolvedAlertCount"] == 6
    assert {alert["instanceId"] for alert in manager_report.json()["unresolvedAlerts"]} == {
        1,
        3,
        4,
        5,
        7,
        9,
    }
