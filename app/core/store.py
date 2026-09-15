"""Short-lived shared state: login counters, revoked tokens, cached diagnoses.

Two backends behind one interface, chosen by `REDIS_URL`:

* **Redis**, when `REDIS_URL` is set. Every worker process and every server reads the same
  keys, which is what a rate limit and a token denylist need once there is more than one
  process — `uvicorn --workers N`, several servers behind a load balancer, or serverless
  instances that share nothing else.
* **Process memory**, when it is empty — the default. Correct for the single-worker
  deployment this project is measured in (docs/operations/DEPLOYMENT.md § 5) and for the
  test suite; each process keeps its own counters, so it is *not* correct for more than one.

Every value here expires on its own, so neither backend needs a cleanup job.

Redis failures fail **open**: a read answers "nothing stored" and a write is dropped, with a
warning logged. An outage of the cache then costs the protection it adds — rate limiting,
revocation, cached answers — but never the API itself, which is the same trade the LLM
fallback makes (docs/design/LLM_FEATURE.md § 2).
"""

import logging
import threading
import time
from collections.abc import Callable

from redis import Redis, RedisError

from app.config import settings

logger = logging.getLogger(__name__)

# A cache call sits on the request path, so a slow Redis must not become a slow API. Half a
# second is far above a healthy round trip and far below the time a caller notices.
REDIS_TIMEOUT_SECONDS = 0.5


class MemoryStore:
    """The in-process backend. Thread-safe: controllers run on AnyIO's worker threadpool."""

    # Expired entries are only swept this often, so a write is not O(keys) every time.
    PURGE_INTERVAL_SECONDS = 60.0

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        # The clock is injectable so a test can move past a window instead of sleeping.
        self._clock = clock
        self._data: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        self._last_purge = clock()

    def _live(self, key: str, now: float) -> tuple[str, float] | None:
        entry = self._data.get(key)
        if entry is not None and entry[1] <= now:
            del self._data[key]
            return None
        return entry

    def _purge(self, now: float) -> None:
        if now - self._last_purge < self.PURGE_INTERVAL_SECONDS:
            return
        self._data = {k: v for k, v in self._data.items() if v[1] > now}
        self._last_purge = now

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._live(key, self._clock())
            return entry[0] if entry else None

    def set(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            now = self._clock()
            self._purge(now)
            self._data[key] = (value, now + ttl)

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def add(self, key: str, amount: int, ttl: int) -> tuple[int, int]:
        """Adds `amount` to a counter and returns `(new value, seconds until it expires)`.

        The window starts when the counter is created and is never extended, so a caller
        that keeps hitting a limit cannot keep itself locked out indefinitely.
        """
        with self._lock:
            now = self._clock()
            self._purge(now)
            entry = self._live(key, now)
            value, expires = (int(entry[0]), entry[1]) if entry else (0, now + ttl)
            value += amount
            self._data[key] = (str(value), expires)
            return value, max(1, round(expires - now))


class RedisStore:
    """The shared backend. Same contract as `MemoryStore`, over a `redis.Redis` client."""

    def __init__(self, client: Redis, prefix: str = "") -> None:
        self._client = client
        self._prefix = prefix

    def _warn(self, operation: str, exc: RedisError) -> None:
        logger.warning("Redis %s failed, continuing without it: %s", operation, exc)

    def get(self, key: str) -> str | None:
        try:
            return self._client.get(self._prefix + key)
        except RedisError as exc:
            self._warn("GET", exc)
            return None

    def set(self, key: str, value: str, ttl: int) -> None:
        try:
            self._client.set(self._prefix + key, value, ex=ttl)
        except RedisError as exc:
            self._warn("SET", exc)

    def exists(self, key: str) -> bool:
        try:
            return bool(self._client.exists(self._prefix + key))
        except RedisError as exc:
            self._warn("EXISTS", exc)
            return False

    def delete(self, key: str) -> None:
        try:
            self._client.delete(self._prefix + key)
        except RedisError as exc:
            self._warn("DEL", exc)

    def add(self, key: str, amount: int, ttl: int) -> tuple[int, int]:
        """`MemoryStore.add` in one round trip.

        `SET … NX EX` creates the counter with its window only if it does not exist yet, and
        `INCRBY` keeps an existing TTL, so the window is fixed at creation exactly as in
        memory. Using `SET NX` rather than `EXPIRE NX` keeps this working on Redis 6. A
        failure answers `(0, 0)` — a counter nobody has touched — which is the fail-open.
        """
        full_key = self._prefix + key
        try:
            pipe = self._client.pipeline()
            pipe.set(full_key, 0, ex=ttl, nx=True)
            pipe.incrby(full_key, amount)
            pipe.ttl(full_key)
            _, value, remaining = pipe.execute()
            return int(value), max(1, int(remaining))
        except RedisError as exc:
            self._warn("INCRBY", exc)
            return 0, 0


Store = MemoryStore | RedisStore

_store: Store | None = None
_store_lock = threading.Lock()


def get_store() -> Store:
    """The process's store, built on first use — the same shape as `llm_service._get_client`.

    Building the Redis client opens no connection; redis-py connects on the first command,
    so a Redis that is down at startup is a logged warning per request, not a failed boot.
    """
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                if settings.REDIS_URL.strip():
                    client = Redis.from_url(
                        settings.REDIS_URL.strip(),
                        decode_responses=True,
                        socket_timeout=REDIS_TIMEOUT_SECONDS,
                        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
                    )
                    _store = RedisStore(client, settings.REDIS_KEY_PREFIX)
                else:
                    _store = MemoryStore()
    return _store
