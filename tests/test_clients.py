"""Functional tests for the client endpoints: registration, listing, cost and SLA.

Rules under test: docs/business-rules/AUTHORIZATION.md, docs/business-rules/COST.md
and docs/business-rules/SLA.md.
"""

from datetime import timedelta

import pytest

from app.core.security import hash_password
from app.models import Client, Member, Role
from app.models.models import utcnow


def _next_month() -> str:
    first_of_month = utcnow().replace(day=1)
    return (first_of_month + timedelta(days=32)).replace(day=1).strftime("%Y-%m")


# --------------------------------------------------------------------------- create


def test_admin_registers_a_client(api, auth_headers):
    client, db = api

    response = client.post(
        "/api/clients",
        headers=auth_headers["admin"],
        json={"clientName": "Hue Manufacturing", "contractPlan": "STANDARD", "managerId": 2},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 11
    assert body["clientName"] == "Hue Manufacturing"
    assert body["contractPlan"] == "STANDARD"
    assert body["managerId"] == 2
    assert db.get(Client, 11) is not None

    # The new client immediately falls inside its manager's scope.
    scoped = client.get("/api/clients", headers=auth_headers["manager1"])
    assert 11 in [item["id"] for item in scoped.json()["items"]]


def test_client_registration_is_admin_only(api, auth_headers):
    client, db = api

    response = client.post(
        "/api/clients",
        headers=auth_headers["manager1"],
        json={"clientName": "Manager Co", "contractPlan": "BASIC", "managerId": 2},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "ADMIN role required"
    assert db.query(Client).count() == 10


def test_client_registration_rejects_a_manager_id_that_is_not_a_manager(api, auth_headers):
    client, _ = api

    response = client.post(
        "/api/clients",
        headers=auth_headers["admin"],
        json={"clientName": "Wrong Owner", "contractPlan": "BASIC", "managerId": 1},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "ValidationError"
    assert "CLIENT_MANAGER" in response.json()["detail"]


def test_client_registration_rejects_an_unknown_manager_id(api, auth_headers):
    client, _ = api

    response = client.post(
        "/api/clients",
        headers=auth_headers["admin"],
        json={"clientName": "Ghost Owner", "contractPlan": "BASIC", "managerId": 999},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "NotFound"
    assert response.json()["detail"] == "Member (manager) 999 not found"


@pytest.mark.parametrize(
    "override",
    [
        pytest.param({"contractPlan": "GOLD"}, id="unknown-plan"),
        pytest.param({"clientName": ""}, id="empty-name"),
        pytest.param({"managerId": "two"}, id="non-numeric-manager"),
    ],
)
def test_client_registration_validates_the_body(api, auth_headers, override):
    client, _ = api
    body = {"clientName": "Validation Co", "contractPlan": "BASIC", "managerId": 2}
    body.update(override)

    response = client.post("/api/clients", headers=auth_headers["admin"], json=body)

    assert response.status_code == 422


# ----------------------------------------------------------------------------- list


def test_client_list_is_scoped_by_role(api, auth_headers):
    client, _ = api

    admin = client.get("/api/clients", headers=auth_headers["admin"])
    manager1 = client.get("/api/clients", headers=auth_headers["manager1"])
    manager2 = client.get("/api/clients", headers=auth_headers["manager2"])

    assert [item["id"] for item in admin.json()["items"]] == list(range(1, 11))
    assert [item["id"] for item in manager1.json()["items"]] == [1, 2, 3, 4, 5]
    assert [item["id"] for item in manager2.json()["items"]] == [6, 7, 8, 9, 10]
    assert admin.json()["items"][0]["clientName"] == "VinaSoft"
    assert admin.json()["items"][0]["contractPlan"] == "PREMIUM"
    assert admin.json()["total"] == 10


def test_a_manager_with_no_clients_sees_nothing(api):
    """An empty scope must match nothing — not everything.

    Every scoped list resolves the caller's clients as a subquery inside its own
    statement (docs/performance/PERFORMANCE_BUGS.md § PERF-10). A manager assigned no
    clients makes that subquery empty, which is the case where a filter is easiest to
    lose: drop it and the caller sees the whole table.
    """
    client, db = api
    db.add(
        Member(
            email="nobody@techvalley.vn",
            password=hash_password("manager123!"),
            name="No Clients",
            role=Role.CLIENT_MANAGER,
        )
    )
    db.commit()
    token = client.post(
        "/api/auth/login",
        json={"email": "nobody@techvalley.vn", "password": "manager123!"},
    ).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    for path in (
        "/api/clients",
        "/api/instances",
        "/api/alerts",
        "/api/monitor/warnings",
        "/api/monitor/errors",
        "/api/monitor/long-stopped",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, path
        assert response.json()["total"] == 0, path
        assert response.json()["items"] == [], path

    report = client.get("/api/monitor/report", headers=headers).json()
    assert report["instanceCountByStatus"] == {"RUNNING": 0, "STOPPED": 0, "ERROR": 0}
    assert report["warningCount"] == 0
    assert report["totalMonthlyCost"] == 0.0
    assert report["unresolvedAlertCount"] == 0


def test_client_instances_are_listed_for_the_owning_manager(api, auth_headers):
    client, _ = api

    response = client.get("/api/clients/1/instances", headers=auth_headers["manager1"])

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [1, 2, 3]
    assert {item["clientId"] for item in response.json()["items"]} == {1}
    assert response.json()["total"] == 3


def test_client_list_is_paginated(api, auth_headers):
    client, _ = api

    first = client.get("/api/clients?page=1&size=4", headers=auth_headers["admin"])
    last = client.get("/api/clients?page=3&size=4", headers=auth_headers["admin"])

    assert [item["id"] for item in first.json()["items"]] == [1, 2, 3, 4]
    assert [item["id"] for item in last.json()["items"]] == [9, 10]
    assert first.json()["total"] == 10
    assert first.json()["totalPages"] == 3


def test_client_list_pagination_counts_only_the_callers_clients(api, auth_headers):
    client, _ = api

    response = client.get("/api/clients?size=2", headers=auth_headers["manager1"])

    # `total` is the scoped count, so a manager is never told how many clients exist.
    assert response.json()["total"] == 5
    assert response.json()["totalPages"] == 3
    assert [item["id"] for item in response.json()["items"]] == [1, 2]


def test_client_instances_are_paginated(api, auth_headers):
    client, _ = api

    first = client.get("/api/clients/1/instances?size=2", headers=auth_headers["manager1"])
    second = client.get(
        "/api/clients/1/instances?page=2&size=2", headers=auth_headers["manager1"]
    )

    assert [item["id"] for item in first.json()["items"]] == [1, 2]
    assert [item["id"] for item in second.json()["items"]] == [3]
    assert first.json()["total"] == 3
    assert first.json()["totalPages"] == 2


def test_cost_and_sla_still_cover_every_instance_not_a_page(api, auth_headers):
    client, _ = api

    cost = client.get("/api/clients/1/cost", headers=auth_headers["manager1"])
    sla = client.get("/api/clients/1/sla", headers=auth_headers["manager1"])

    # These two embed a row per instance and are deliberately not paginated, so the
    # page bound on /instances must not have leaked into them.
    assert cost.json()["instanceCount"] == 3
    assert len(cost.json()["costByInstance"]) == 3
    assert len(sla.json()["instanceDetails"]) == 3


@pytest.mark.parametrize(
    "path", ["/instances", "/cost", "/cost-forecast", "/sla"]
)
def test_client_sub_resources_enforce_scope_and_existence(api, auth_headers, path):
    client, _ = api

    forbidden = client.get(f"/api/clients/6{path}", headers=auth_headers["manager1"])
    missing = client.get(f"/api/clients/999{path}", headers=auth_headers["admin"])

    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "CLIENT_MANAGER can only access clients assigned to them"
    assert missing.status_code == 404
    assert missing.json()["error"] == "NotFound"


# ------------------------------------------------------------------------------ cost


def test_current_cost_sums_every_instance_regardless_of_status(api, auth_headers):
    client, _ = api

    response = client.get("/api/clients/1/cost", headers=auth_headers["manager1"])

    assert response.status_code == 200
    body = response.json()
    assert body["clientId"] == 1
    assert body["clientName"] == "VinaSoft"
    assert body["month"] == utcnow().strftime("%Y-%m")
    assert body["instanceCount"] == 3
    # 250 (LARGE) + 250 (LARGE) + 120 (MEDIUM, STOPPED — still billed)
    assert body["totalMonthlyCost"] == 620.0
    assert [row["instanceId"] for row in body["costByInstance"]] == [1, 2, 3]
    assert body["costByInstance"][2] == {
        "instanceId": 3,
        "instanceName": "vinasoft-batch-01",
        "instanceType": "MEDIUM",
        "status": "STOPPED",
        "monthlyCost": 120.0,
    }


def test_current_cost_follows_a_newly_registered_instance(api, auth_headers):
    client, _ = api

    before = client.get("/api/clients/1/cost", headers=auth_headers["manager1"]).json()
    client.post(
        "/api/instances",
        headers=auth_headers["manager1"],
        json={
            "instanceName": "vinasoft-cache-01",
            "region": "ap-southeast-1",
            "instanceType": "SMALL",
            "clientId": 1,
        },
    )
    after = client.get("/api/clients/1/cost", headers=auth_headers["manager1"]).json()

    assert after["instanceCount"] == before["instanceCount"] + 1
    assert after["totalMonthlyCost"] == before["totalMonthlyCost"] + 50.0


def test_forecast_counts_only_running_instances(api, auth_headers):
    client, _ = api

    response = client.get("/api/clients/1/cost-forecast", headers=auth_headers["manager1"])

    assert response.status_code == 200
    body = response.json()
    assert body["forecastMonth"] == _next_month()
    # Instances 1 and 2 are RUNNING LARGE; instance 3 is STOPPED and excluded.
    assert body["runningInstanceCount"] == 2
    assert body["forecastCost"] == 500.0
    assert body["breakdown"] == {"LARGE": {"count": 2, "unitPrice": 250.0, "subtotal": 500.0}}


def test_forecast_reacts_to_a_status_change(api, auth_headers):
    client, _ = api

    client.patch(
        "/api/instances/3/status",
        headers=auth_headers["manager1"],
        json={"status": "RUNNING", "cpuUsage": 10.0},
    )
    response = client.get("/api/clients/1/cost-forecast", headers=auth_headers["manager1"])

    body = response.json()
    assert body["runningInstanceCount"] == 3
    assert body["forecastCost"] == 620.0
    assert body["breakdown"]["MEDIUM"] == {"count": 1, "unitPrice": 120.0, "subtotal": 120.0}


def test_forecast_of_a_client_without_running_instances_is_zero(api, auth_headers):
    client, _ = api

    # GreenEnergy VN (client 8) owns one STOPPED instance.
    response = client.get("/api/clients/8/cost-forecast", headers=auth_headers["manager2"])

    assert response.status_code == 200
    assert response.json()["runningInstanceCount"] == 0
    assert response.json()["forecastCost"] == 0.0
    assert response.json()["breakdown"] == {}


# ------------------------------------------------------------------------------- SLA


def test_sla_reports_full_uptime_when_every_instance_is_running(api, auth_headers):
    client, _ = api

    # Mekong Foods (client 4, STANDARD) owns one RUNNING instance.
    response = client.get("/api/clients/4/sla", headers=auth_headers["manager1"])

    assert response.status_code == 200
    body = response.json()
    assert body["contractPlan"] == "STANDARD"
    assert body["slaThreshold"] == 99.0
    assert body["month"] == utcnow().strftime("%Y-%m")
    assert body["uptimePercent"] == 100.0
    assert body["isViolation"] is False
    assert [row["instanceId"] for row in body["instanceDetails"]] == [8]
    assert body["instanceDetails"][0]["uptimePercent"] == 100.0


def test_sla_flags_a_violation_for_a_long_stopped_instance(api, auth_headers):
    client, _ = api

    # Saigon Retail (client 3, BASIC 95%) owns one RUNNING and one instance stopped
    # 120 hours ago, which always drags the average below the threshold.
    response = client.get("/api/clients/3/sla", headers=auth_headers["manager1"])

    assert response.status_code == 200
    body = response.json()
    assert body["slaThreshold"] == 95.0
    assert body["isViolation"] is True
    assert 0.0 <= body["uptimePercent"] < 95.0

    details = {row["instanceId"]: row for row in body["instanceDetails"]}
    assert details[6]["status"] == "RUNNING"
    assert details[6]["uptimePercent"] == 100.0
    assert details[7]["status"] == "STOPPED"
    assert details[7]["uptimePercent"] < 100.0
    assert details[7]["runningHours"] <= details[7]["measuredHours"]


def test_sla_of_a_client_without_instances_is_not_a_violation(api, auth_headers):
    client, _ = api
    created = client.post(
        "/api/clients",
        headers=auth_headers["admin"],
        json={"clientName": "Empty Co", "contractPlan": "PREMIUM", "managerId": 2},
    )

    response = client.get(f"/api/clients/{created.json()['id']}/sla", headers=auth_headers["admin"])

    assert response.status_code == 200
    assert response.json()["slaThreshold"] == 99.9
    assert response.json()["uptimePercent"] == 100.0
    assert response.json()["isViolation"] is False
    assert response.json()["instanceDetails"] == []
