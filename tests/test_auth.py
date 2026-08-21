"""Functional tests for the health check and the authentication layer.

Covers POST /api/auth/login and the JWT guard every other endpoint depends on.
Rules under test: docs/api/AUTHENTICATION.md and docs/api/ERRORS.md section 2.2.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings

# One representative endpoint per router; all of them sit behind get_current_member.
PROTECTED_ENDPOINTS = [
    ("get", "/api/instances"),
    ("get", "/api/instances/1"),
    ("get", "/api/instances/1/diagnosis"),
    ("get", "/api/monitor/report"),
    ("get", "/api/alerts"),
    ("get", "/api/clients"),
    ("get", "/api/clients/1/cost"),
    ("get", "/api/clients/1/cost-forecast"),
    ("get", "/api/clients/1/sla"),
]


def _token(**claims) -> str:
    payload = {
        "sub": "1",
        "email": "admin@techvalley.vn",
        "role": "ADMIN",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    payload.update(claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_health_check_is_public(api):
    client, _ = api

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["docs"] == "/docs"


def test_login_returns_a_usable_token_with_role_and_name(api):
    client, _ = api

    response = client.post(
        "/api/auth/login",
        json={"email": "admin@techvalley.vn", "password": "admin123!"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tokenType"] == "bearer"
    assert body["role"] == "ADMIN"
    assert body["name"] == "TechValley Admin"

    claims = jwt.decode(body["accessToken"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert claims["sub"] == "1"
    assert claims["email"] == "admin@techvalley.vn"
    assert claims["role"] == "ADMIN"
    assert claims["exp"] > datetime.now(timezone.utc).timestamp()

    # The token actually authorises a protected call.
    authorised = client.get(
        "/api/clients",
        headers={"Authorization": f"Bearer {body['accessToken']}"},
    )
    assert authorised.status_code == 200


def test_login_issues_the_manager_role_for_a_manager_account(api):
    client, _ = api

    response = client.post(
        "/api/auth/login",
        json={"email": "lam@techvalley.vn", "password": "manager123!"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "CLIENT_MANAGER"
    assert response.json()["name"] == "Thai Van Lam"


@pytest.mark.parametrize(
    "email,password",
    [
        ("admin@techvalley.vn", "wrong-password"),
        ("nobody@techvalley.vn", "admin123!"),
    ],
)
def test_login_rejects_bad_credentials_without_revealing_which_part_failed(api, email, password):
    client, _ = api

    response = client.post("/api/auth/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_rejects_a_malformed_email(api):
    client, _ = api

    response = client.post("/api/auth/login", json={"email": "not-an-email", "password": "x"})

    assert response.status_code == 422


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_protected_endpoints_reject_a_missing_token(api, method, path):
    client, _ = api

    response = getattr(client, method)(path)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated. Provide a Bearer token."


@pytest.mark.parametrize(
    "token,detail",
    [
        pytest.param("not-a-jwt", "Invalid token", id="malformed"),
        pytest.param(
            jwt.encode({"sub": "1"}, "the-wrong-secret", algorithm="HS256"),
            "Invalid token",
            id="signed-with-another-secret",
        ),
    ],
)
def test_invalid_tokens_are_rejected(api, token, detail):
    client, _ = api

    response = client.get("/api/clients", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["detail"] == detail


def test_expired_token_is_rejected(api):
    client, _ = api
    expired = _token(exp=datetime.now(timezone.utc) - timedelta(seconds=1))

    response = client.get("/api/clients", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Token has expired"


def test_token_for_a_member_that_no_longer_exists_is_rejected(api):
    client, _ = api
    orphaned = _token(sub="999", email="ghost@techvalley.vn")

    response = client.get("/api/clients", headers={"Authorization": f"Bearer {orphaned}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Member no longer exists"
