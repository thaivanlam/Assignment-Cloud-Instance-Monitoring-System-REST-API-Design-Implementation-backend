from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if IS_SQLITE else {}

# An in-memory SQLite URL gets a SingletonThreadPool, which has no overflow to size.
IS_MEMORY_SQLITE = IS_SQLITE and (
    ":memory:" in settings.DATABASE_URL
    or settings.DATABASE_URL.rstrip("/") == "sqlite:"
)

# Every controller is declared `def`, so FastAPI runs it in AnyIO's worker threadpool,
# whose default limit is 40 — and `get_db` holds one connection for the whole request.
# The pool is therefore sized to serve 40 handlers at once: 20 connections kept open and
# 20 more opened on demand. On QueuePool's defaults (5 + 10 = 15) the 16th concurrent
# request waited 30 seconds in `pool.connect()` and then failed with a 500. See
# docs/performance/PERFORMANCE_BUGS.md § PERF-02.
MAX_CONCURRENT_REQUESTS = 40
POOL_SIZE = MAX_CONCURRENT_REQUESTS // 2
MAX_OVERFLOW = MAX_CONCURRENT_REQUESTS - POOL_SIZE

pool_args = (
    {}
    if IS_MEMORY_SQLITE
    else {
        "pool_size": POOL_SIZE,
        "max_overflow": MAX_OVERFLOW,
        # A connection idle since the last burst may have been closed at the other end;
        # pre-ping replaces it instead of failing the request that borrowed it.
        "pool_pre_ping": True,
    }
)

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, **pool_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        """Put every SQLite connection in WAL mode with a relaxed sync setting.

        SQLite's default rollback journal locks the *whole database file* for the
        duration of a write, so a monitoring scan recording an alert blocks every
        concurrent reader until its commit has fsynced. WAL lets readers carry on
        against the last committed snapshot while a writer works, and
        `synchronous=NORMAL` drops the fsync-per-commit that made the stall long.
        Both are per-connection settings, so they are set on connect rather than once.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
