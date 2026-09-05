import functools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import seed as seed_module
from app.core.security import hash_password
from app.database import Base, get_db
from app.models import Member, Role
from app.main import app
from app.seed import seed


@pytest.fixture(scope="session", autouse=True)
def memoised_seed_hashing():
    """Hash each demo password once per session instead of once per test.

    Seeding runs for every test and hashes three passwords at 260,000 PBKDF2
    iterations, which otherwise accounts for most of the suite's runtime. Only the
    seed is memoised — `verify_password` still does the real work on every login, and
    `hash_password` itself is exercised through it.
    """
    original = seed_module.hash_password
    seed_module.hash_password = functools.lru_cache(maxsize=None)(original)
    try:
        yield
    finally:
        seed_module.hash_password = original


@pytest.fixture
def api():
    """Isolated API and database for every test.

    StaticPool keeps one in-memory SQLite database available to both pytest and
    FastAPI's worker thread.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # The same arguments as the application's factory, `expire_on_commit=False`
    # included, so the suite exercises the session semantics the API runs on.
    testing_session = sessionmaker(
        autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
    )
    Base.metadata.create_all(bind=engine)
    db = testing_session()
    seed(db)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client, db
    finally:
        client.close()
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
        # StaticPool holds its connection open until the engine is disposed. Without
        # this, every test leaves a live in-memory database behind and the suite gets
        # progressively slower.
        engine.dispose()


@pytest.fixture
def auth_headers(api):
    client, _ = api

    def login(email: str, password: str) -> dict[str, str]:
        response = client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['accessToken']}"}

    return {
        "admin": login("admin@techvalley.vn", "admin123!"),
        "manager1": login("lam@techvalley.vn", "manager123!"),
        "manager2": login("minh@techvalley.vn", "manager123!"),
    }


@pytest.fixture
def empty_scope_headers(api):
    """Bearer headers for a CLIENT_MANAGER the seed assigns no clients to.

    The scope of such a caller is empty, which is the case both authorization guards are
    easiest to get wrong: an empty scope has to keep meaning *nothing*, where losing the
    check entirely makes it mean *everything*
    (docs/business-rules/AUTHORIZATION.md, docs/performance/PERFORMANCE_BUGS.md
    § PERF-10 and § PERF-11).
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
    return {"Authorization": f"Bearer {token}"}
