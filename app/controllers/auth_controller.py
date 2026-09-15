import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_token_claims
from app.core.rate_limit import release_login_attempt, reserve_login_attempt
from app.core.revocation import revoke_token
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models import Member
from app.schemas.schemas import LoginRequest, TokenResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login (JWT token issuance)",
    responses={429: {"description": "Too many failed login attempts; see `Retry-After`"}},
)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # Behind a reverse proxy this is the proxy's address unless uvicorn runs with
    # `--proxy-headers` — docs/operations/DEPLOYMENT.md § 5.
    client_ip = request.client.host if request.client else "unknown"
    reserve_login_attempt(body.email, client_ip)

    member = db.query(Member).filter(Member.email == body.email).first()
    if member is None or not verify_password(body.password, member.password):
        logger.warning("Failed login for %s from %s", body.email, client_ip)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    release_login_attempt(body.email, client_ip)
    token = create_access_token(member.id, member.email, member.role.value)
    return TokenResponse(accessToken=token, role=member.role, name=member.name)


@router.post(
    "/logout",
    status_code=204,
    summary="Logout (revoke the current token)",
)
def logout(claims: dict = Depends(get_token_claims)):
    # Revokes only the token on this request; the member's other sessions stay valid.
    revoke_token(claims)
