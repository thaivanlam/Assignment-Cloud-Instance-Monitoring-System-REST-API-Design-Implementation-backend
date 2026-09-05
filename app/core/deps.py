import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, aliased

from app.core.security import decode_access_token
from app.database import get_db
from app.models import Client, Member, Role

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_member(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Member:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    member = db.get(Member, int(payload["sub"]))
    if member is None:
        raise HTTPException(status_code=401, detail="Member no longer exists")
    return member


def require_admin(member: Member = Depends(get_current_member)) -> Member:
    if member.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="ADMIN role required")
    return member


def assert_client_access(member: Member, client: Client) -> None:
    """ADMIN can access every client; CLIENT_MANAGER only their assigned clients."""
    if member.role == Role.ADMIN:
        return
    if client.managerId != member.id:
        raise HTTPException(
            status_code=403,
            detail="CLIENT_MANAGER can only access clients assigned to them",
        )


def accessible_client_ids(member: Member) -> Select[tuple[int]] | None:
    """Returns None for ADMIN (no filter), otherwise a SELECT of the manager's client ids.

    A `SELECT` rather than a list: the caller drops it straight into an `IN`, so the scope
    is resolved inside the statement that was going to run anyway instead of costing a
    round trip of its own before it. Fetching the ids first made every `CLIENT_MANAGER`
    request pay an extra query whose only output was a bind-parameter list
    (docs/performance/PERFORMANCE_BUGS.md § PERF-10).

    The subquery is built over an alias, so it keeps its own `FROM clients` and cannot be
    correlated away when the enclosing query is itself over `clients` — `list_clients` is
    exactly that case.

    A manager with no clients needs no sentinel. The call sites used to write
    `.in_(client_ids or [-1])`, spending an id that can never match on an empty list; a
    subquery that selects no rows matches nothing on its own.
    """
    if member.role == Role.ADMIN:
        return None
    scope = aliased(Client)
    return select(scope.id).where(scope.managerId == member.id)


def assert_client_id_access(db: Session, member: Member, client_id: int) -> None:
    """`assert_client_access` given only the client's id, without loading the client.

    Every caller that holds an `Instance` already holds `instance.clientId`, but reaching
    `instance.client` to compare one integer fired a lazy load — a whole `clients` row
    fetched and turned into an ORM object per request, and two chained loads on the
    alert path (docs/performance/PERFORMANCE_BUGS.md § PERF-11).

    So the question is asked of the database instead of the identity map: is this id in
    the scope `accessible_client_ids` builds? One `EXISTS`, which SQLite answers with a
    single primary-key seek, and nothing is loaded. An ADMIN's scope is `None` — every
    client — so an ADMIN pays no statement at all.

    Use `assert_client_access` where the `Client` is in hand for another reason; the two
    apply the same rule and raise the same 403.
    """
    scope = accessible_client_ids(member)
    if scope is None:
        return

    # The scope selects exactly one column, the aliased `clients.id`, so narrowing it to
    # one id is a `WHERE` on that column rather than a second copy of the scope rule.
    scope_id = scope.selected_columns.id
    if not db.scalar(select(scope.where(scope_id == client_id).exists())):
        raise HTTPException(
            status_code=403,
            detail="CLIENT_MANAGER can only access clients assigned to them",
        )
