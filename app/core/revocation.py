"""Access-token revocation — docs/api/AUTHENTICATION.md § 3, SEC-04.

A token stays stateless: nothing is stored when one is issued. Only a *revoked* token is
recorded, by its `jti`, for exactly as long as the token itself would still be accepted —
after its `exp` the signature check rejects it anyway, so the entry expires with it and the
denylist never holds more than the tokens revoked within the last token lifetime.
"""

from datetime import datetime, timezone

from app.core.store import get_store


def _key(jti: str) -> str:
    return f"revoked:{jti}"


def revoke_token(claims: dict) -> None:
    """Denylists a decoded token until its own expiry."""
    remaining = int(claims["exp"] - datetime.now(timezone.utc).timestamp())
    if remaining > 0:
        get_store().set(_key(claims["jti"]), "1", ttl=remaining)


def is_token_revoked(jti: str) -> bool:
    return get_store().exists(_key(jti))
