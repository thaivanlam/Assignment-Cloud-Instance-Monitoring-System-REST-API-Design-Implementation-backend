"""Login rate limiting — docs/api/AUTHENTICATION.md § 2, SEC-05.

Failed logins are counted in fixed windows of `LOGIN_WINDOW_SECONDS`, twice over: per target
account, which a distributed attacker cannot vary, and per client address, which stops one
source spraying many accounts. A request over either limit is refused with `429` *before*
the password is checked, so a blocked guess costs the server no PBKDF2 work (PERF-13).

The attempt is counted up front and handed back on success, rather than counted after it
fails. Checking first and counting afterwards lets a burst of concurrent guesses all pass the
check before any of them is recorded; reserving first makes the limit hold under
concurrency, because the increment itself is the check.
"""

from fastapi import HTTPException, status

from app.config import settings
from app.core.store import get_store

TOO_MANY_ATTEMPTS = "Too many failed login attempts. Try again later."


def _keys(email: str, client_ip: str) -> tuple[str, str]:
    # Lower-cased so `Admin@…` and `admin@…` share one counter instead of doubling it.
    return f"login:account:{email.strip().lower()}", f"login:ip:{client_ip}"


def reserve_login_attempt(email: str, client_ip: str) -> None:
    """Counts one attempt against both limits; raises `429` if either is exceeded."""
    store = get_store()
    window = settings.LOGIN_WINDOW_SECONDS
    account_key, ip_key = _keys(email, client_ip)

    account_count, account_retry = store.add(account_key, 1, window)
    ip_count, ip_retry = store.add(ip_key, 1, window)

    blocked = [
        retry
        for count, limit, retry in (
            (account_count, settings.LOGIN_MAX_FAILURES_PER_ACCOUNT, account_retry),
            (ip_count, settings.LOGIN_MAX_FAILURES_PER_IP, ip_retry),
        )
        if count > limit
    ]
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=TOO_MANY_ATTEMPTS,
            headers={"Retry-After": str(max(blocked))},
        )


def release_login_attempt(email: str, client_ip: str) -> None:
    """Undoes the reservation of a login that succeeded.

    The account counter is cleared outright: a user who mistyped nine times and then got in
    starts from zero. The address counter only gives back this one attempt, so logging in to
    an account one owns does not wipe the failures an address ran up against other accounts.
    """
    store = get_store()
    account_key, ip_key = _keys(email, client_ip)
    store.delete(account_key)
    store.add(ip_key, -1, settings.LOGIN_WINDOW_SECONDS)
