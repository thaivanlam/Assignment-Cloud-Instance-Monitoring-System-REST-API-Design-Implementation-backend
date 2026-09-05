"""Functional tests for the instance endpoints.

Covers POST /api/instances, the list conventions (pagination / filter / sort),
GET /api/instances/{id}, PATCH /{id}/status and DELETE /{id}.
Rules under test: docs/business-rules/INSTANCE_LIFECYCLE.md,
docs/business-rules/AUTHORIZATION.md and docs/api/CONVENTIONS.md.
"""

import pytest

from app.models import Alert, Instance


def _ids(response) -> list[int]:
    return [item["id"] for item in response.json()["items"]]


# --------------------------------------------------------------------------- create


def test_create_instance_derives_cost_and_applies_defaults(api, auth_headers):
    client, db = api

    response = client.post(
        "/api/instances",
        headers=auth_headers["manager1"],
        json={
            "instanceName": "vinasoft-cache-01",
            "region": "ap-southeast-1",
            "instanceType": "MEDIUM",
            "clientId": 1,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 16
    assert body["instanceName"] == "vinasoft-cache-01"
    # monthlyCost is derived from the type, never taken from the request.
    assert body["monthlyCost"] == 120.0
    # Schema defaults.
    assert body["status"] == "RUNNING"
    assert body["cpuUsage"] == 0.0
    assert db.get(Instance, 16) is not None


@pytest.mark.parametrize(
    "instance_type,expected_cost",
    [("SMALL", 50.0), ("MEDIUM", 120.0), ("LARGE", 250.0)],
)
def test_create_instance_prices_every_type(api, auth_headers, instance_type, expected_cost):
    client, _ = api

    response = client.post(
        "/api/instances",
        headers=auth_headers["admin"],
        json={
            "instanceName": f"priced-{instance_type.lower()}",
            "region": "ap-southeast-1",
            "instanceType": instance_type,
            "clientId": 1,
        },
    )

    assert response.status_code == 201
    assert response.json()["monthlyCost"] == expected_cost


def test_create_instance_is_blocked_for_another_managers_client(api, auth_headers):
    client, db = api

    response = client.post(
        "/api/instances",
        headers=auth_headers["manager1"],
        json={
            "instanceName": "not-mine-01",
            "region": "ap-southeast-1",
            "instanceType": "SMALL",
            "clientId": 6,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "CLIENT_MANAGER can only access clients assigned to them"
    assert db.query(Instance).count() == 15


def test_create_instance_rejects_an_unknown_client(api, auth_headers):
    client, _ = api

    response = client.post(
        "/api/instances",
        headers=auth_headers["admin"],
        json={
            "instanceName": "orphan-01",
            "region": "ap-southeast-1",
            "instanceType": "SMALL",
            "clientId": 999,
        },
    )

    assert response.status_code == 404
    assert response.json()["error"] == "NotFound"
    assert response.json()["detail"] == "Client 999 not found"


@pytest.mark.parametrize(
    "override",
    [
        pytest.param({"cpuUsage": 150.0}, id="cpu-above-100"),
        pytest.param({"cpuUsage": -1.0}, id="cpu-below-0"),
        pytest.param({"instanceType": "HUGE"}, id="unknown-type"),
        pytest.param({"status": "PAUSED"}, id="unknown-status"),
        pytest.param({"instanceName": ""}, id="empty-name"),
    ],
)
def test_create_instance_validates_the_body(api, auth_headers, override):
    client, _ = api
    body = {
        "instanceName": "validation-01",
        "region": "ap-southeast-1",
        "instanceType": "SMALL",
        "clientId": 1,
    }
    body.update(override)

    response = client.post("/api/instances", headers=auth_headers["admin"], json=body)

    assert response.status_code == 422


# ----------------------------------------------------------------------------- list


def test_list_instances_paginates(api, auth_headers):
    client, _ = api

    first = client.get("/api/instances?page=1&size=5", headers=auth_headers["admin"])
    last = client.get("/api/instances?page=3&size=5", headers=auth_headers["admin"])
    beyond = client.get("/api/instances?page=4&size=5", headers=auth_headers["admin"])

    assert first.status_code == 200
    assert first.json()["total"] == 15
    assert first.json()["page"] == 1
    assert first.json()["size"] == 5
    assert first.json()["totalPages"] == 3
    assert _ids(first) == [1, 2, 3, 4, 5]
    assert _ids(last) == [11, 12, 13, 14, 15]
    # A page past the end is an empty page, not an error.
    assert beyond.status_code == 200
    assert _ids(beyond) == []
    assert beyond.json()["total"] == 15


@pytest.mark.parametrize(
    "query,expected",
    [
        pytest.param("status=ERROR", [5, 9], id="status"),
        pytest.param("status=STOPPED", [3, 7, 13], id="status-stopped"),
        pytest.param("region=ap-northeast-2", [3, 9, 13], id="region"),
        pytest.param("instanceType=LARGE", [1, 2, 9, 10, 11], id="type"),
        pytest.param("clientId=2", [4, 5], id="client"),
        pytest.param("clientId=1&status=RUNNING", [1, 2], id="client-and-status"),
    ],
)
def test_list_instances_filters(api, auth_headers, query, expected):
    client, _ = api

    response = client.get(f"/api/instances?size=100&{query}", headers=auth_headers["admin"])

    assert response.status_code == 200
    assert _ids(response) == expected
    assert response.json()["total"] == len(expected)


def test_list_instances_sorts(api, auth_headers):
    client, _ = api

    descending = client.get("/api/instances?size=100&sort=-cpuUsage", headers=auth_headers["admin"])
    by_name = client.get("/api/instances?size=100&sort=instanceName", headers=auth_headers["admin"])
    unknown_field = client.get("/api/instances?size=100&sort=nope", headers=auth_headers["admin"])

    cpu_values = [item["cpuUsage"] for item in descending.json()["items"]]
    assert cpu_values == sorted(cpu_values, reverse=True)
    assert _ids(descending)[0] == 14  # health-api-01 at 96.3%

    names = [item["instanceName"] for item in by_name.json()["items"]]
    assert names == sorted(names)

    # An unsortable field silently falls back to id rather than failing the request.
    assert unknown_field.status_code == 200
    assert _ids(unknown_field) == list(range(1, 16))


def test_pages_partition_a_non_unique_sort_without_gaps_or_repeats(api, auth_headers):
    client, _ = api

    # `status` has three distinct values across 15 instances, so almost every row is
    # tied with several others. Walking the pages must still visit each row once.
    walked = []
    for page in (1, 2, 3, 4):
        response = client.get(
            f"/api/instances?sort=status&page={page}&size=4", headers=auth_headers["admin"]
        )
        walked.extend(_ids(response))

    assert sorted(walked) == list(range(1, 16))
    everything = client.get("/api/instances?size=100&sort=status", headers=auth_headers["admin"])
    assert walked == _ids(everything)


@pytest.mark.parametrize(
    "query", ["page=0", "size=0", "size=101", "status=BOGUS", "instanceType=BOGUS"]
)
def test_list_instances_validates_query_parameters(api, auth_headers, query):
    client, _ = api

    response = client.get(f"/api/instances?{query}", headers=auth_headers["admin"])

    assert response.status_code == 422


def test_list_instances_is_scoped_to_the_callers_clients(api, auth_headers):
    client, _ = api

    manager1 = client.get("/api/instances?size=100", headers=auth_headers["manager1"])
    manager2 = client.get("/api/instances?size=100", headers=auth_headers["manager2"])

    assert manager1.json()["total"] == 9
    assert _ids(manager1) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert manager2.json()["total"] == 6
    assert _ids(manager2) == [10, 11, 12, 13, 14, 15]


def test_filtering_by_another_managers_client_returns_nothing(api, auth_headers):
    """The scope filter is applied on top of clientId, so the filter cannot be used to
    read across the boundary."""
    client, _ = api

    response = client.get("/api/instances?clientId=6", headers=auth_headers["manager1"])

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert _ids(response) == []


# ------------------------------------------------------------------------ read one


def test_get_instance_returns_the_full_record(api, auth_headers):
    client, _ = api

    response = client.get("/api/instances/1", headers=auth_headers["manager1"])

    assert response.status_code == 200
    body = response.json()
    assert body["instanceName"] == "vinasoft-web-01"
    assert body["region"] == "ap-southeast-1"
    assert body["instanceType"] == "LARGE"
    assert body["status"] == "RUNNING"
    assert body["cpuUsage"] == 91.5
    assert body["monthlyCost"] == 250.0
    assert body["clientId"] == 1


def test_get_instance_enforces_scope_and_existence(api, auth_headers):
    client, _ = api

    forbidden = client.get("/api/instances/10", headers=auth_headers["manager1"])
    missing = client.get("/api/instances/999", headers=auth_headers["admin"])

    assert forbidden.status_code == 403
    assert missing.status_code == 404
    assert missing.json()["error"] == "NotFound"
    assert missing.json()["detail"] == "Instance 999 not found"


def test_a_manager_with_no_clients_reaches_no_single_instance(api, empty_scope_headers):
    """An empty scope must forbid every single-object endpoint, not wave them through.

    The guard on these four asks the database whether the instance's `clientId` is in the
    caller's scope rather than loading the client to compare `managerId`
    (docs/performance/PERFORMANCE_BUGS.md § PERF-11). A caller who owns no clients is the
    case that separates "the scope is empty" from "there is no scope": the first must be
    403 on every one of them, and instance 1 is left untouched to prove the writes were
    rejected before they ran.
    """
    client, db = api
    headers = empty_scope_headers

    responses = {
        "get": client.get("/api/instances/1", headers=headers),
        "status": client.patch(
            "/api/instances/1/status", headers=headers, json={"status": "STOPPED"}
        ),
        "delete": client.delete("/api/instances/13", headers=headers),
        "diagnosis": client.get("/api/instances/6/diagnosis", headers=headers),
    }

    for name, response in responses.items():
        assert response.status_code == 403, name
        assert response.json()["detail"] == (
            "CLIENT_MANAGER can only access clients assigned to them"
        ), name
    assert db.get(Instance, 1).status.value == "RUNNING"
    assert db.get(Instance, 13) is not None


# --------------------------------------------------------------------- status update


def test_stopping_an_instance_resets_cpu_and_advances_updated_at(api, auth_headers):
    client, db = api
    before = db.get(Instance, 1).updatedAt

    response = client.patch(
        "/api/instances/1/status",
        headers=auth_headers["manager1"],
        json={"status": "STOPPED"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "STOPPED"
    # A stopped instance reports no CPU load, even though none was sent.
    assert response.json()["cpuUsage"] == 0.0
    assert db.get(Instance, 1).updatedAt > before


def test_status_update_keeps_an_explicit_cpu_value(api, auth_headers):
    client, _ = api

    response = client.patch(
        "/api/instances/2/status",
        headers=auth_headers["manager1"],
        json={"status": "RUNNING", "cpuUsage": 77.7},
    )

    assert response.status_code == 200
    assert response.json()["cpuUsage"] == 77.7
    # monthlyCost is not touched by a status change.
    assert response.json()["monthlyCost"] == 250.0


def test_status_update_validates_its_body(api, auth_headers):
    client, _ = api

    out_of_range = client.patch(
        "/api/instances/1/status",
        headers=auth_headers["manager1"],
        json={"status": "RUNNING", "cpuUsage": 150},
    )
    unknown_status = client.patch(
        "/api/instances/1/status",
        headers=auth_headers["manager1"],
        json={"status": "PAUSED"},
    )
    missing_status = client.patch(
        "/api/instances/1/status",
        headers=auth_headers["manager1"],
        json={},
    )

    assert out_of_range.status_code == 422
    assert unknown_status.status_code == 422
    assert missing_status.status_code == 422


def test_status_update_on_an_unknown_instance_is_404(api, auth_headers):
    client, _ = api

    response = client.patch(
        "/api/instances/999/status",
        headers=auth_headers["admin"],
        json={"status": "STOPPED"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "NotFound"


# --------------------------------------------------------------------------- delete


def test_running_instance_cannot_be_deleted(api, auth_headers):
    client, db = api

    blocked = client.delete("/api/instances/1", headers=auth_headers["manager1"])

    assert blocked.status_code == 409
    assert blocked.json()["error"] == "ActiveInstanceException"
    assert blocked.json()["detail"] == (
        "Instance 1 is RUNNING and cannot be deleted. Stop it first."
    )
    assert db.get(Instance, 1) is not None


def test_instance_is_deleted_once_stopped(api, auth_headers):
    client, db = api

    stopped = client.patch(
        "/api/instances/1/status",
        headers=auth_headers["manager1"],
        json={"status": "STOPPED"},
    )
    deleted = client.delete("/api/instances/1", headers=auth_headers["manager1"])
    gone = client.get("/api/instances/1", headers=auth_headers["manager1"])

    assert stopped.status_code == 200
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert gone.status_code == 404
    assert db.get(Instance, 1) is None


def test_deleting_an_instance_removes_its_alerts(api, auth_headers):
    client, db = api

    # The warning scan records a CPU_HIGH alert for instance 1.
    client.get("/api/monitor/warnings", headers=auth_headers["manager1"])
    assert db.query(Alert).filter(Alert.instanceId == 1).count() == 1

    client.patch(
        "/api/instances/1/status",
        headers=auth_headers["manager1"],
        json={"status": "STOPPED"},
    )
    deleted = client.delete("/api/instances/1", headers=auth_headers["manager1"])

    assert deleted.status_code == 204
    assert db.query(Alert).filter(Alert.instanceId == 1).count() == 0


def test_delete_enforces_scope_and_existence(api, auth_headers):
    client, db = api

    # Instance 13 is STOPPED, so only the scope check can reject this.
    forbidden = client.delete("/api/instances/13", headers=auth_headers["manager1"])
    missing = client.delete("/api/instances/999", headers=auth_headers["admin"])

    assert forbidden.status_code == 403
    assert db.get(Instance, 13) is not None
    assert missing.status_code == 404
