"""Functional tests for the health check and the authentication layer.

Covers POST /api/auth/login, its rate limit, POST /api/auth/logout, and the JWT guard every
other endpoint depends on — on both store backends.
Rules under test: docs/api/AUTHENTICATION.md and docs/api/ERRORS.md section 2.2.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.controllers import auth_controller

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
    ("post", "/api/auth/logout"),
]


def _token(**claims) -> str:
    payload = {
        "sub": "1",
        "email": "admin@techvalley.vn",
        "role": "ADMIN",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "jti": uuid.uuid4().hex,
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
    assert claims["iat"] <= datetime.now(timezone.utc).timestamp()
    assert len(claims["jti"]) == 32

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
        pytest.param(
            jwt.encode(
                {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                settings.SECRET_KEY,
                algorithm=settings.ALGORITHM,
            ),
            "Invalid token",
            id="no-jti-so-not-revocable",
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


# ---------- login rate limit (SEC-05) ----------

ADMIN_EMAIL = "admin@techvalley.vn"


def _login(client, email=ADMIN_EMAIL, password="admin123!"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_is_refused_once_an_account_reaches_its_failure_limit(api, monkeypatch):
    client, _ = api
    limit = settings.LOGIN_MAX_FAILURES_PER_ACCOUNT

    # The counter ignores case, so varying it does not buy an attacker extra guesses.
    for attempt in range(limit):
        email = ADMIN_EMAIL if attempt % 2 else "Admin@techvalley.vn"
        assert _login(client, email, "wrong-password").status_code == 401

    checked = []
    real_verify = auth_controller.verify_password
    monkeypatch.setattr(
        auth_controller,
        "verify_password",
        lambda *args: checked.append(args) or real_verify(*args),
    )

    # Even the right password is refused now, and it is refused before it is checked.
    blocked = _login(client)

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many failed login attempts. Try again later."
    assert 0 < int(blocked.headers["Retry-After"]) <= settings.LOGIN_WINDOW_SECONDS
    assert checked == []


def test_the_account_limit_lifts_when_its_window_ends(api, clock):
    client, _ = api
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_ACCOUNT):
        _login(client, password="wrong-password")
    assert _login(client).status_code == 429

    clock.advance(settings.LOGIN_WINDOW_SECONDS)

    assert _login(client).status_code == 200


def test_a_successful_login_clears_the_account_counter(api):
    client, _ = api
    limit = settings.LOGIN_MAX_FAILURES_PER_ACCOUNT

    for _ in range(limit - 1):
        _login(client, password="wrong-password")
    assert _login(client).status_code == 200

    # A full allowance again, not the one attempt that was left.
    statuses = [_login(client, password="wrong-password").status_code for _ in range(limit)]
    assert statuses == [401] * limit


def test_one_address_is_limited_across_many_accounts(api, monkeypatch):
    client, _ = api
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES_PER_IP", 3)

    statuses = [
        _login(client, f"guess{n}@techvalley.vn", "admin123!").status_code for n in range(4)
    ]

    assert statuses == [401, 401, 401, 429]


def test_successful_logins_do_not_use_up_the_address_limit(api, monkeypatch):
    client, _ = api
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES_PER_IP", 3)

    # Many people behind one office address, all typing their password correctly.
    statuses = [_login(client).status_code for _ in range(6)]

    assert statuses == [200] * 6


# ---------- logout and revocation (SEC-04, SEC-08) ----------


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_logout_revokes_the_token_it_was_called_with(api):
    client, _ = api
    token = _login(client).json()["accessToken"]
    assert client.get("/api/clients", headers=_bearer(token)).status_code == 200

    response = client.post("/api/auth/logout", headers=_bearer(token))

    assert response.status_code == 204
    assert response.content == b""
    for call in (
        client.get("/api/clients", headers=_bearer(token)),
        client.post("/api/auth/logout", headers=_bearer(token)),
    ):
        assert call.status_code == 401
        assert call.json()["detail"] == "Token has been revoked"


def test_logout_leaves_the_members_other_sessions_valid(api):
    client, _ = api
    laptop = _login(client).json()["accessToken"]
    phone = _login(client).json()["accessToken"]

    client.post("/api/auth/logout", headers=_bearer(laptop))

    assert client.get("/api/clients", headers=_bearer(laptop)).status_code == 401
    assert client.get("/api/clients", headers=_bearer(phone)).status_code == 200


def test_a_revocation_is_kept_only_as_long_as_the_token_lives(api, store, clock):
    client, _ = api
    token = _login(client).json()["accessToken"]
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    client.post("/api/auth/logout", headers=_bearer(token))
    assert store.exists(f"revoked:{claims['jti']}")

    clock.advance(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 1)

    # By now the token is rejected as expired, so the denylist entry has nothing to do.
    assert not store.exists(f"revoked:{claims['jti']}")


# ---------- the Redis backend ----------


def test_rate_limit_and_revocation_share_state_through_redis(api, redis_server):
    client, _ = api
    limit = settings.LOGIN_MAX_FAILURES_PER_ACCOUNT
    token = _login(client).json()["accessToken"]

    for _ in range(limit):
        _login(client, password="wrong-password")
    assert _login(client).status_code == 429
    assert client.post("/api/auth/logout", headers=_bearer(token)).status_code == 204
    assert client.get("/api/clients", headers=_bearer(token)).status_code == 401

    # The state is in Redis, under the configured prefix, and every key expires.
    keys = redis_server.client.keys("*")
    prefix = settings.REDIS_KEY_PREFIX
    assert f"{prefix}login:account:{ADMIN_EMAIL}" in keys
    assert any(key.startswith(f"{prefix}revoked:") for key in keys)
    assert all(redis_server.client.ttl(key) > 0 for key in keys)


def test_a_redis_outage_fails_open(api, redis_server):
    """Losing Redis costs the protection it adds, never the API: logins, logout and
    authenticated calls all keep answering."""
    client, _ = api
    token = _login(client).json()["accessToken"]
    redis_server.server.connected = False

    attempts = settings.LOGIN_MAX_FAILURES_PER_ACCOUNT + 1
    wrong = [_login(client, password="wrong-password").status_code for _ in range(attempts)]

    assert wrong == [401] * attempts
    assert _login(client).status_code == 200
    assert client.post("/api/auth/logout", headers=_bearer(token)).status_code == 204
    assert client.get("/api/clients", headers=_bearer(token)).status_code == 200
